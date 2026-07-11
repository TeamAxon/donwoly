from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.schemas import UserProfile
from database import get_db
from models import User
from users.schemas import ProfileUpdateRequest


router = APIRouter(prefix="/api/users", tags=["users"])
CurrentUser = Annotated[User, Depends(get_current_user)]
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=UserProfile)
def get_my_profile(user: CurrentUser) -> UserProfile:
    return UserProfile.model_validate(user)


@router.patch("/me", response_model=UserProfile)
def update_my_profile(
    payload: ProfileUpdateRequest, user: CurrentUser, db: DatabaseSession
) -> UserProfile:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field in {"region", "industry"}:
            value = value.value
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return UserProfile.model_validate(user)
