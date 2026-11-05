"""Schema pieces shared by more than one router."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class NonNullableUpdate(BaseModel):
    """A PATCH body that refuses an explicit null for a required column.

    The update schemas type every field as `X | None = None` so that "omitted"
    means "leave alone", which also lets a caller send null. For a nullable
    column that clears it; for a NOT NULL one it would reach the database as a
    500 (or, for a departure's time, a misleading collision). `non_nullable`
    names those columns, and sending one as null is a 422 instead.
    """

    non_nullable: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _refuse_explicit_null(self):
        for name in self.non_nullable:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self


def blank_is_null(value: str | None) -> str | None:
    """Stripped, and blank is null: a title or group name nobody typed."""
    if value is None:
        return None
    return value.strip() or None


class NoteLinkFields(BaseModel):
    """One link on a note, in either direction: a URL and an optional title."""

    url: str
    title: str | None = None

    _title = field_validator("title")(blank_is_null)

    @field_validator("url")
    @classmethod
    def _stripped_url(cls, value: str) -> str:
        """Stripped; a blank one refused rather than silently dropped, so a
        caller that sent an empty row learns it did."""
        url = value.strip()
        if not url:
            raise ValueError("a link cannot be blank")
        return url


class NoteLinkResponse(NoteLinkFields):
    model_config = ConfigDict(from_attributes=True)
