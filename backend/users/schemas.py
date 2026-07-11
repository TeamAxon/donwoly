from pydantic import BaseModel, Field, field_validator, model_validator

from auth.schemas import Industry, Region


class ProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=20)
    age: int | None = Field(default=None, ge=18, le=99)
    region: Region | None = None
    industry: Industry | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 2 <= len(value) <= 20:
            raise ValueError("이름은 2~20자여야 합니다.")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("수정할 필드가 최소 1개 필요합니다.")
        return self
