from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import CurrentUser, current_user
from app.db import Database, get_db
from app.repos.profiles import PgProfileRepo, ProfileRepo, UnknownBrandError
from app.schemas.profile import ProfileIn, ProfileOut
from app.units import from_cm

router = APIRouter(prefix="/v1/profile", tags=["profile"])


def get_profile_repo(db: Database = Depends(get_db)) -> ProfileRepo:
    return PgProfileRepo(db)


@router.get("", response_model=ProfileOut)
async def read_profile(
    user: CurrentUser = Depends(current_user),
    repo: ProfileRepo = Depends(get_profile_repo),
) -> ProfileOut:
    stored = await repo.get(user.id)
    if stored is None:
        # The web app sends first-time users to /preferences on 404.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No profile yet.")
    m = stored.measurements_cm
    display = {dim: from_cm(m[dim], stored.unit) if dim in m else None for dim in ("waist", "inseam", "hips")}
    return ProfileOut(unit=stored.unit, brands=stored.brands, updated_at=stored.updated_at, **display)


@router.put("", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def save_profile(
    body: ProfileIn,
    user: CurrentUser = Depends(current_user),
    repo: ProfileRepo = Depends(get_profile_repo),
) -> None:
    try:
        await repo.save(
            user.id,
            unit=body.unit,
            measurements_cm=body.measurements_cm(),
            brand_ids=body.brand_ids,
        )
    except UnknownBrandError:
        raise HTTPException(422, detail="Unknown brand.") from None
