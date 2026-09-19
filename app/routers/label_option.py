"""The category and bag suggestions: listing them, tidying them, pruning them.

These are suggestions, not references. Everything here follows from that one
fact - see `docs/business-rules.md`.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import LabelKind
from app.database import get_db
from app.models import LabelOption
from app.schemas.label_option import LabelOptionResponse, LabelOptionUpdate
from app.services.domain.packing import count_items_using, rename_option

router = APIRouter(prefix="/api/label-options", tags=["Common options"])

NOT_FOUND = "Option not found."


def _get(db: Session, option_id: int) -> LabelOption:
    option = db.get(LabelOption, option_id)
    if option is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return option


def _as_response(db: Session, option: LabelOption) -> LabelOptionResponse:
    response = LabelOptionResponse.model_validate(option)
    response.usage_count = count_items_using(db, option)
    return response


@router.get("", response_model=list[LabelOptionResponse])
def index(kind: LabelKind | None = None, db: Session = Depends(get_db)):
    query = select(LabelOption).order_by(LabelOption.kind, LabelOption.position)
    if kind is not None:
        query = query.where(LabelOption.kind == kind)
    return [
        _as_response(db, option) for option in db.execute(query).scalars().all()
    ]


@router.patch("/{option_id}", response_model=LabelOptionResponse)
def update(option_id: int, payload: LabelOptionUpdate, db: Session = Depends(get_db)):
    option = _get(db, option_id)
    changes = payload.model_dump(exclude_unset=True)

    if "position" in changes and changes["position"] is not None:
        option.position = changes["position"]

    if changes.get("value"):
        # A rename onto an existing value is a merge, which deletes THIS row
        # rather than updating it. So the response is built by looking up
        # whichever row survives, which is the same query either way - rather
        # than by asking the session whether this object still exists, which
        # depends on flush timing.
        kind, new_value = option.kind, changes["value"]
        rename_option(db, option, new_value)
        db.commit()
        option = db.execute(
            select(LabelOption).where(
                LabelOption.kind == kind, LabelOption.value == new_value
            )
        ).scalar_one()
    else:
        db.commit()
        db.refresh(option)

    return _as_response(db, option)


@router.delete("/{option_id}", status_code=204)
def delete(option_id: int, db: Session = Depends(get_db)):
    """Prune a suggestion. The items using it are deliberately left alone.

    Deleting is about autocomplete and nothing else: blanking the field on an
    item that legitimately carries the value would turn tidying the list into
    losing data.
    """
    option = _get(db, option_id)
    db.delete(option)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
