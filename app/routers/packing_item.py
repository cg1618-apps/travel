"""Items on a list.

Two path shapes rather than one prefix: an item is created under the list that
owns it, and addressed on its own afterwards. A single `APIRouter` prefix
cannot express both, so the paths are written out in full.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PackingItem, PackingList
from app.schemas.packing_item import (
    PackingItemCreate,
    PackingItemResponse,
    PackingItemUpdate,
)

router = APIRouter(tags=["Packing items"])

NOT_FOUND = "Packing item not found."


def _get(db: Session, item_id: int) -> PackingItem:
    item = db.get(PackingItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return item


def _next_position(db: Session, list_id: int) -> int:
    """One past the end of THIS list.

    Scoped to the list rather than global: a shared counter would leave a new
    list's first item at position 400 and sort correctly by accident, until
    something started comparing positions between lists.
    """
    highest = db.execute(
        select(func.max(PackingItem.position)).where(PackingItem.list_id == list_id)
    ).scalar()
    return 0 if highest is None else highest + 1


@router.post(
    "/api/packing-lists/{list_id}/items",
    response_model=PackingItemResponse,
    status_code=201,
)
def create(list_id: int, payload: PackingItemCreate, db: Session = Depends(get_db)):
    if db.get(PackingList, list_id) is None:
        raise HTTPException(status_code=404, detail="Packing list not found.")

    item = PackingItem(
        list_id=list_id, position=_next_position(db, list_id), **payload.model_dump()
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/api/packing-items/{item_id}", response_model=PackingItemResponse)
def update(item_id: int, payload: PackingItemUpdate, db: Session = Depends(get_db)):
    item = _get(db, item_id)
    # `exclude_unset` rather than `exclude_none`: null is a legitimate value
    # here - clearing a category, or saying a quantity does not apply - and
    # excluding it would make those fields impossible to unset.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/api/packing-items/{item_id}", status_code=204)
def delete(item_id: int, db: Session = Depends(get_db)):
    item = _get(db, item_id)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
