from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg
from asyncpg.pool import PoolConnectionProxy

from app.db import Database
from app.pipeline.fit_profile import FitProfile, Measurement, ProfileUpdate
from app.pipeline.models import Basis, Dimension, FitCategory, FitMode, QuickSize, SizeSystem
from app.schemas.profile import Brand
from app.units import Unit


class UnknownBrandError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class StoredProfile:
    unit: Unit
    fit: FitProfile
    brands: list[Brand]
    updated_at: datetime

    @property
    def measurements_cm(self) -> dict[str, float]:
        return {d.value: m.value_cm for d, m in self.fit.measurements.items()}


class ProfileRepo(Protocol):
    async def get(self, user_id: UUID) -> StoredProfile | None: ...

    async def save(
        self, user_id: UUID, *, unit: Unit, update: ProfileUpdate, brand_ids: list[UUID] | None
    ) -> None:
        """Sections left as None in the update, and brand_ids=None, keep what is stored."""
        ...


_GET = """
select p.unit,
       p.updated_at,
       p.fit_mode,
       p.size_system,
       coalesce((select jsonb_object_agg(q.category, q.size)
                   from quick_sizes q where q.user_id = p.user_id), '{}') as quick_sizes,
       coalesce((select jsonb_object_agg(m.dimension, jsonb_build_object(
                          'value_cm', m.value_cm, 'basis', m.basis, 'note', m.garment_note))
                   from fit_measurements m where m.user_id = p.user_id), '{}') as measurements,
       coalesce((select jsonb_agg(jsonb_build_object('id', b.id, 'name', b.name, 'slug', b.slug)
                                  order by b.name)
                   from brand_preferences bp join brands b on b.id = bp.brand_id
                  where bp.user_id = p.user_id), '[]') as brands
  from profiles p
 where p.user_id = $1
"""

_UPSERT_PROFILE = """
insert into profiles (user_id, unit, fit_mode, size_system) values ($1, $2, $3, $4)
on conflict (user_id) do update
   set unit = excluded.unit,
       fit_mode = excluded.fit_mode,
       size_system = coalesce(excluded.size_system, profiles.size_system)
"""

# Cleared optional dimensions (e.g. hips) are deleted rather than kept stale.
_DELETE_MISSING_MEASUREMENTS = """
delete from fit_measurements where user_id = $1 and dimension <> all($2::text[])
"""

_UPSERT_MEASUREMENTS = """
insert into fit_measurements (user_id, dimension, value_cm, basis, garment_note)
select $1, d, v, b::measurement_basis, n
  from unnest($2::text[], $3::numeric[], $4::text[], $5::text[]) as t(d, v, b, n)
on conflict (user_id, dimension) do update
   set value_cm = excluded.value_cm, basis = excluded.basis, garment_note = excluded.garment_note
 where (fit_measurements.value_cm, fit_measurements.basis, fit_measurements.garment_note)
       is distinct from (excluded.value_cm, excluded.basis, excluded.garment_note)
"""

_DELETE_MISSING_QUICK_SIZES = """
delete from quick_sizes where user_id = $1 and category::text <> all($2::text[])
"""

_UPSERT_QUICK_SIZES = """
insert into quick_sizes (user_id, category, size)
select $1, c::fit_category, s::quick_size from unnest($2::text[], $3::text[]) as t(c, s)
on conflict (user_id, category) do update set size = excluded.size
 where quick_sizes.size is distinct from excluded.size
"""


def _fit_from_row(row: asyncpg.Record) -> FitProfile:
    measurements: dict[str, dict[str, Any]] = row["measurements"]
    return FitProfile(
        mode=FitMode(row["fit_mode"]),
        size_system=SizeSystem(row["size_system"]) if row["size_system"] else None,
        quick_sizes={FitCategory(c): QuickSize(s) for c, s in row["quick_sizes"].items()},
        measurements={
            Dimension(d): Measurement(float(m["value_cm"]), Basis(m["basis"]), m["note"])
            for d, m in measurements.items()
        },
    )


async def _save_measurements(
    conn: "PoolConnectionProxy[asyncpg.Record]", user_id: UUID, measurements: dict[Dimension, Measurement]
) -> None:
    dims = [d.value for d in measurements]
    await conn.execute(_DELETE_MISSING_MEASUREMENTS, user_id, dims)
    await conn.execute(
        _UPSERT_MEASUREMENTS,
        user_id,
        dims,
        [m.value_cm for m in measurements.values()],
        [m.basis.value for m in measurements.values()],
        [m.note for m in measurements.values()],
    )


async def _save_quick_sizes(
    conn: "PoolConnectionProxy[asyncpg.Record]", user_id: UUID, sizes: dict[FitCategory, QuickSize]
) -> None:
    categories = [c.value for c in sizes]
    await conn.execute(_DELETE_MISSING_QUICK_SIZES, user_id, categories)
    await conn.execute(_UPSERT_QUICK_SIZES, user_id, categories, [s.value for s in sizes.values()])


async def _save_brands(
    conn: "PoolConnectionProxy[asyncpg.Record]", user_id: UUID, brand_ids: list[UUID]
) -> None:
    # A CTE delete and insert would see the same snapshot and conflict on the PK,
    # so brands are replaced with two statements in the same transaction.
    await conn.execute("delete from brand_preferences where user_id = $1", user_id)
    if brand_ids:
        await conn.execute(
            "insert into brand_preferences (user_id, brand_id) select $1, unnest($2::uuid[])",
            user_id,
            brand_ids,
        )


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
            fit=_fit_from_row(row),
            brands=[Brand.model_validate(b) for b in row["brands"]],
            updated_at=row["updated_at"],
        )

    async def save(
        self, user_id: UUID, *, unit: Unit, update: ProfileUpdate, brand_ids: list[UUID] | None
    ) -> None:
        size_system = update.size_system.value if update.size_system else None
        try:
            async with self._db.user_tx(user_id) as conn:
                await conn.execute(_UPSERT_PROFILE, user_id, unit.value, update.mode.value, size_system)
                if update.measurements is not None:
                    await _save_measurements(conn, user_id, dict(update.measurements))
                if update.quick_sizes is not None:
                    await _save_quick_sizes(conn, user_id, dict(update.quick_sizes))
                if brand_ids is not None:
                    await _save_brands(conn, user_id, brand_ids)
        except asyncpg.ForeignKeyViolationError as exc:
            if exc.constraint_name and "brand_id" in exc.constraint_name:
                raise UnknownBrandError from exc
            raise
