from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db import Database, get_db
from app.repos.brands import BrandRepo, PgBrandRepo
from app.schemas.profile import Brand

router = APIRouter(prefix="/v1/brands", tags=["brands"])


def get_brand_repo(db: Database = Depends(get_db)) -> BrandRepo:
    return PgBrandRepo(db)


@router.get("", response_model=list[Brand])
async def search_brands(
    q: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    repo: BrandRepo = Depends(get_brand_repo),
) -> list[Brand]:
    """Public catalog lookup for the "+ Add brand" combobox."""
    return await repo.search(q.strip() if q else None, limit)
