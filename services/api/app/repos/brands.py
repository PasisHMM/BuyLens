from typing import Protocol

from app.db import Database
from app.schemas.profile import Brand


class BrandRepo(Protocol):
    async def search(self, query: str | None, limit: int) -> list[Brand]: ...


def _like_pattern(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class PgBrandRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def search(self, query: str | None, limit: int) -> list[Brand]:
        async with self._db.public_tx() as conn:
            rows = await conn.fetch(
                """
                select id, name, slug from brands
                 where $1::text is null or name ilike $1
                 order by name
                 limit $2
                """,
                _like_pattern(query) if query else None,
                limit,
            )
        return [Brand(id=r["id"], name=r["name"], slug=r["slug"]) for r in rows]
