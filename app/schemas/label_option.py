"""The remembered values behind the free-text fields."""

from pydantic import BaseModel, ConfigDict, Field


class LabelOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    value: str
    position: int
    #: How many items currently carry this value. The rename screen says this
    #: before it rewrites anything, which is the difference between a rename
    #: and a surprise.
    usage_count: int = 0


class LabelOptionUpdate(BaseModel):
    value: str | None = Field(default=None, min_length=1)
    position: int | None = Field(default=None, ge=0)
