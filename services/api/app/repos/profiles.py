from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from app.db import Database
from app.schemas.profile import Brand
from app.units import Unit


class UnknownBrandError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class StoredProfile:
    unit: Unit
    measurements_cm: dict[str, float]
    brands: list[Brand]
    updated_at: datetime


class ProfileRepo(Protocol):
    async def get(self, user_id: UUID) -> StoredProfile | None: ...

    async def save(
        self, user_id: UUID, *, unit: Unit, measurements_cm: dict[str, float], brand_ids: list[UUID]
    ) -> None: ...


_GET = """
select p.unit,
       p.updated_at,
       coalesce((select jsonb_object_agg(m.dimension, m.value_cm)
                   from fit_measurements m where m.user_id = p.user_id), '{}') as measurements,
       coalesce((select jsonb_agg(jsonb_build_object('id', b.id, 'name', b.name, 'slug', b.slug)
                                  order by b.name)
                   from brand_preferences bp join brands b on b.id = bp.brand_id
                  where bp.user_id = p.user_id), '[]') as brands
  from profiles p
 where p.user_id = $1
"""

_UPSERT_PROFILE = """
insert into profiles (user_id, unit) values ($1, $2)
on conflict (user_id) do update set unit = excluded.unit
"""

# Cleared optional dimensions (e.g. hips) are deleted rather than kept stale.
_DELETE_MISSING_MEASUREMENTS = """
delete from fit_measurements where user_id = $1 and dimension <> all($2::text[])
"""

_UPSERT_MEASUREMENTS = """
insert into fit_measurements (user_id, dimension, value_cm)
select $1, d, v from unnest($2::text[], $3::numeric[]) as t(d, v)
on conflict (user_id, dimension) do update
   set value_cm = excluded.value_cm
 where fit_measurements.value_cm is distinct from excluded.value_cm
"""


class PgProfileRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, user_id: UUID) -> StoredProfile | None:
        async with self._db.user_tx(user_id) as conn:
            row = await conn.fetchrow(_GET, user_id)
        if row is None:
            return None
        return StoredProfile(
            unit=Unit(row["unit"]),
            measurements_cm={k: float(v) for k, v in row["measurements"].items()},
            brands=[Brand.model_validate(b) for b in row["brands"]],
            updated_at=row["updated_at"],
        )

    async def save(
        self, user_id: UUID, *, unit: Unit, measurements_cm: dict[str, float], brand_ids: list[UUID]
    ) -> None:
        dims, values = list(measurements_cm), list(measurements_cm.values())
        try:
            async with self._db.user_tx(user_id) as conn:
                await conn.execute(_UPSERT_PROFILE, user_id, unit.value)
                await conn.execute(_DELETE_MISSING_MEASUREMENTS, user_id, dims)
                await conn.execute(_UPSERT_MEASUREMENTS, user_id, dims, values)
                # A CTE delete and insert would see the same snapshot and conflict on the PK,
                # so brands are replaced with two statements in the same transaction.
                await conn.execute("delete from brand_preferences where user_id = $1", user_id)
                if brand_ids:
                    await conn.execute(
                        "insert into brand_preferences (user_id, brand_id) select $1, unnest($2::uuid[])",
                        user_id,
                        brand_ids,
                    )
        except asyncpg.ForeignKeyViolationError as exc:
            if exc.constraint_name and "brand_id" in exc.constraint_name:
                raise UnknownBrandError from exc
            raise
