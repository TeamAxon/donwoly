from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
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

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(user: CurrentUser, db: DatabaseSession) -> Response:
    """
    현재 로그인한 사용자의 계정을 삭제한다.
    User 모델의 conversations 관계와 DB FK CASCADE에 의해 대화/메시지도 함께 삭제된다.
    Qdrant 지식 데이터는 사용자 데이터가 아니므로 삭제하지 않는다.
    """
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

