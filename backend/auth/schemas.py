import re
import uuid
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Region(str, Enum):
    SYDNEY = "SYDNEY"
    MELBOURNE = "MELBOURNE"
    BRISBANE = "BRISBANE"
    PERTH = "PERTH"
    GOLD_COAST = "GOLD_COAST"
    OTHER = "OTHER"


class Industry(str, Enum):
    FARM = "FARM"
    HOSPITALITY = "HOSPITALITY"
    CONSTRUCTION = "CONSTRUCTION"
    CLEANING = "CLEANING"
    FACTORY = "FACTORY"
    OFFICE = "OFFICE"
    TOURISM = "TOURISM"
    OTHER = "OTHER"


class SignupRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=20)
    password: str = Field(min_length=8)
    age: int = Field(ge=18, le=99)
    region: Region
    industry: Industry

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not 2 <= len(value) <= 20:
            raise ValueError("이름은 2~20자여야 합니다.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("비밀번호에는 영문이 최소 1개 필요합니다.")
        if not re.search(r"[0-9]", value):
            raise ValueError("비밀번호에는 숫자가 최소 1개 필요합니다.")
        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError("비밀번호에는 특수문자가 최소 1개 필요합니다.")
        return value


class SignupResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: uuid.UUID = Field(serialization_alias="userId")
    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    age: int
    region: Region
    industry: Industry


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")
    user: UserProfile


class EmailAvailabilityResponse(BaseModel):
    available: bool
