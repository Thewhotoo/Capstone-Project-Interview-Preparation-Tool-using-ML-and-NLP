"""
Validation for signup and profile updates.

Signup arrives as multipart form data (it carries the resume file), so
every value starts life as a string; pydantic's lax mode converts
"8.4" -> 8.4, "2021" -> 2021, "true"/"on" -> True, "2004-05-12" -> date.

`ProfileFields` holds every student-profile rule once; `SignupRequest`
adds the account fields, and a profile update re-validates the merged
(existing + changed) profile against the same model.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_PATTERN = re.compile(r"^\+?\d{10,15}$")
_PHONE_SEPARATORS = re.compile(r"[\s\-().]")

MIN_AGE = 13
MAX_AGE = 100
MIN_YEAR = 1950
MAX_FUTURE_GRADUATION_YEARS = 8

ScoreType = Literal["percentage", "cgpa"]


def password_problem(password: str) -> str | None:
    """Why a password isn't acceptable, or None. Shared by signup and
    change-password so both enforce the same rules."""
    if not 8 <= len(password) <= 128:
        return "password must be between 8 and 128 characters"
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "password must contain at least one letter and one digit"
    return None


def _max_score(score_type: str) -> float:
    return 100.0 if score_type == "percentage" else 10.0


class ProfileFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    full_name: str = Field(min_length=2, max_length=100)
    date_of_birth: date
    phone: str

    class10_board: str = Field(min_length=2, max_length=100)
    class10_score: float = Field(ge=0)
    class10_score_type: ScoreType
    class10_year: int

    higher_secondary_type: Literal["class12", "diploma"]
    higher_secondary_board: str = Field(min_length=2, max_length=150)
    higher_secondary_score: float = Field(ge=0)
    higher_secondary_score_type: ScoreType
    higher_secondary_year: int

    college: str = Field(min_length=2, max_length=200)
    degree: str = Field(min_length=2, max_length=100)
    branch: str = Field(min_length=2, max_length=100)
    cgpa: float = Field(ge=0)
    cgpa_scale: float
    graduation_year: int

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        phone = _PHONE_SEPARATORS.sub("", value)
        if not _PHONE_PATTERN.match(phone):
            raise ValueError("enter a valid phone number (10-15 digits, optional leading +)")
        return phone

    @field_validator("date_of_birth")
    @classmethod
    def _plausible_age(cls, value: date) -> date:
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if not MIN_AGE <= age <= MAX_AGE:
            raise ValueError(f"age must be between {MIN_AGE} and {MAX_AGE}")
        return value

    @field_validator("cgpa_scale")
    @classmethod
    def _known_scale(cls, value: float) -> float:
        if value not in (4, 10):
            raise ValueError("CGPA scale must be 4 or 10")
        return value

    @model_validator(mode="after")
    def _cross_field_checks(self) -> "ProfileFields":
        current_year = date.today().year
        if self.class10_score > _max_score(self.class10_score_type):
            raise ValueError(f"class10_score cannot exceed {_max_score(self.class10_score_type):g} for {self.class10_score_type}")
        if self.higher_secondary_score > _max_score(self.higher_secondary_score_type):
            raise ValueError(
                f"higher_secondary_score cannot exceed {_max_score(self.higher_secondary_score_type):g} "
                f"for {self.higher_secondary_score_type}"
            )
        if self.cgpa > self.cgpa_scale:
            raise ValueError(f"cgpa cannot exceed the CGPA scale ({self.cgpa_scale:g})")
        if not MIN_YEAR <= self.class10_year <= current_year:
            raise ValueError("class10_year is not a valid year")
        if not self.class10_year <= self.higher_secondary_year <= current_year:
            raise ValueError("higher_secondary_year must be between class10_year and this year")
        if not self.higher_secondary_year <= self.graduation_year <= current_year + MAX_FUTURE_GRADUATION_YEARS:
            raise ValueError("graduation_year must be after higher_secondary_year and at most "
                             f"{MAX_FUTURE_GRADUATION_YEARS} years from now")
        if self.class10_year <= self.date_of_birth.year:
            raise ValueError("class10_year must be after the year of birth")
        return self


class SignupRequest(ProfileFields):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    consent_data: bool
    consent_training: bool = False

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        email = value.lower()
        if not _EMAIL_PATTERN.match(email):
            raise ValueError("enter a valid email address")
        return email

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        problem = password_problem(value)
        if problem:
            raise ValueError(problem)
        return value

    @field_validator("consent_data")
    @classmethod
    def _consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("you must agree to data storage to create an account")
        return value

    def profile_fields(self) -> dict:
        return self.model_dump(include=set(ProfileFields.model_fields))


def validation_errors(error: ValidationError) -> list[dict]:
    """Flatten a pydantic error into `[{field, message}]` for the API
    response. Cross-field errors have no single field and report `field: null`."""
    errors = []
    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"]) or None
        message = item["msg"].removeprefix("Value error, ")
        errors.append({"field": field, "message": message})
    return errors
