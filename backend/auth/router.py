from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.schemas import (
    EmailAvailabilityResponse,
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
    UserProfile,
)
from auth.security import create_access_token, create_refresh_token, hash_password, verify_password
from database import get_db
from models import User


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _tokens(user_id):
    return create_access_token(user_id), create_refresh_token(user_id)


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    if db.scalar(select(User.id).where(User.email == str(payload.email))):
        raise HTTPException(status_code=409, detail={"error": "EMAIL_TAKEN"})

    user = User(
        email=str(payload.email),
        name=payload.name,
        password_hash=hash_password(payload.password),
        age=payload.age,
        region=payload.region.value,
        industry=payload.industry.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"error": "EMAIL_TAKEN"}) from None
    db.refresh(user)

    # TODO(spec 6): Add email_verified and verification flow if email authentication is adopted.
    access_token, refresh_token = _tokens(user.id)
    return SignupResponse(
        user_id=user.id, access_token=access_token, refresh_token=refresh_token
    )


@router.get("/check-email", response_model=EmailAvailabilityResponse)
def check_email(
    email: EmailStr = Query(...), db: Session = Depends(get_db)
) -> EmailAvailabilityResponse:
    normalized_email = str(email).lower()
    exists = db.scalar(select(User.id).where(User.email == normalized_email)) is not None
    return EmailAvailabilityResponse(available=not exists)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"error": "INVALID_CREDENTIALS"})

    access_token, refresh_token = _tokens(user.id)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserProfile.model_validate(user),
    )
