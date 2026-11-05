from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import CurrentUser, current_user
from app.db import Database, get_db
from app.pipeline.fit_profile import InvalidProfile, merge_profile
from app.pipeline.models import Dimension
from app.repos.profiles import PgProfileRepo, ProfileRepo, StoredProfile, UnknownBrandError
from app.schemas.profile import MeasurementOut, ProfileIn, ProfileOut
from app.units import Unit, from_cm

router = APIRouter(prefix="/v1/profile", tags=["profile"])


def get_profile_repo(db: Database = Depends(get_db)) -> ProfileRepo:
    return PgProfileRepo(db)


def _profile_out(stored: StoredProfile) -> ProfileOut:
    fit = stored.fit
    display = {d: from_cm(m.value_cm, stored.unit) for d, m in fit.measurements.items()}
    return ProfileOut(
        unit=stored.unit,
        fit_mode=fit.mode,
        size_system=fit.size_system,
        quick_sizes=fit.quick_sizes,
        measurements=[
            MeasurementOut(dimension=d, value=display[d], basis=m.basis, note=m.note)
            for d, m in fit.measurements.items()
        ],
        waist=display.get(Dimension.WAIST),
        inseam=display.get(Dimension.INSEAM),
        hips=display.get(Dimension.HIPS),
        brands=stored.brands,
        updated_at=stored.updated_at,
    )


@router.get("", response_model=ProfileOut)
async def read_profile(
    user: CurrentUser = Depends(current_user),
    repo: ProfileRepo = Depends(get_profile_repo),
) -> ProfileOut:
    stored = await repo.get(user.id)
    if stored is None:
        # The web app treats 404 as a first-time visitor and offers Quick Fit on the homepage.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No profile yet.")
    return _profile_out(stored)


@router.put("", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def save_profile(
    body: ProfileIn,
    user: CurrentUser = Depends(current_user),
    repo: ProfileRepo = Depends(get_profile_repo),
) -> None:
    stored = await repo.get(user.id)
    update = body.to_update()
    try:
        merge_profile(stored.fit if stored else None, update)
    except InvalidProfile as exc:
        raise HTTPException(422, detail=str(exc)) from None
    unit = body.unit or (stored.unit if stored else Unit.CM)
    try:
        await repo.save(user.id, unit=unit, update=update, brand_ids=body.brands_to_save())
    except UnknownBrandError:
        raise HTTPException(422, detail="Unknown brand.") from None
