from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth.security import decode_access_token
from database import get_db
from models import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"error": "UNAUTHORIZED"})

    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=401, detail={"error": "UNAUTHORIZED"}) from None

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"error": "UNAUTHORIZED"})
    return user
