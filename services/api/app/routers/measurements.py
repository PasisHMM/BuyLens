from fastapi import APIRouter

from app.schemas.measurements import Catalog, build_catalog

router = APIRouter(prefix="/v1/measurements", tags=["measurements"])


@router.get("", response_model=Catalog)
async def read_catalog() -> Catalog:
    return build_catalog()
