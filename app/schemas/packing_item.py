"""What an item looks like going in and coming out."""

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Status, Timing


class PackingItemBase(BaseModel):
    name: str = Field(min_length=1)
    category: str | None = None
    bag: str | None = None
    # `ge=0` on both: a negative count is not a state, and the database has no
    # constraint saying so. Over-packing deliberately IS allowed, so there is
    # no check that `quantity_packed <= quantity`.
    quantity: int | None = Field(default=None, ge=0)
    quantity_packed: int = Field(default=0, ge=0)
    unit: str | None = None
    # Typed as the enums so an unknown value is a 422 with a usable message,
    # rather than reaching the database and coming back as a 500 from a
    # constraint violation.
    status: Status = Status.NOT_PACKED
    timing: Timing = Timing.WHENEVER
    needs_double_check: bool = False
    double_checked: bool = False
    notes: str | None = None


class PackingItemCreate(PackingItemBase):
    pass


class PackingItemUpdate(BaseModel):
    """Every field optional: PATCH changes what it names and nothing else."""

    name: str | None = Field(default=None, min_length=1)
    category: str | None = None
    bag: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    quantity_packed: int | None = Field(default=None, ge=0)
    unit: str | None = None
    status: Status | None = None
    timing: Timing | None = None
    needs_double_check: bool | None = None
    double_checked: bool | None = None
    notes: str | None = None
    position: int | None = Field(default=None, ge=0)


class PackingItemResponse(PackingItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    list_id: int
    position: int
