"""Items on a list.

Two path shapes rather than one prefix: an item is created under the list that
owns it, and addressed on its own afterwards. A single `APIRouter` prefix
cannot express both, so the paths are written out in full.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PackingItem, PackingList
from app.schemas.packing_item import (
    PackingItemBulkCreate,
    PackingItemCreate,
    PackingItemResponse,
    PackingItemUpdate,
)
from app.services.domain.labels import remember_item_labels
from app.services.domain.packing import insert_after, place_in_group

router = APIRouter(tags=["Packing items"])

NOT_FOUND = "Packing item not found."
LIST_NOT_FOUND = "Packing list not found."


def _get(db: Session, item_id: int) -> PackingItem:
    item = db.get(PackingItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return item


def _get_list(db: Session, list_id: int) -> PackingList:
    packing_list = db.get(PackingList, list_id)
    if packing_list is None:
        raise HTTPException(status_code=404, detail=LIST_NOT_FOUND)
    return packing_list


@router.post(
    "/api/packing-lists/{list_id}/items",
    response_model=PackingItemResponse,
    status_code=201,
)
def create(list_id: int, payload: PackingItemCreate, db: Session = Depends(get_db)):
    _get_list(db, list_id)

    fields = payload.model_dump(exclude={"after_id"})
    if payload.after_id is None:
        position = place_in_group(db, list_id, payload.category)
    else:
        after = db.get(PackingItem, payload.after_id)
        if after is None or after.list_id != list_id:
            raise HTTPException(status_code=404, detail="Item to insert after not found on this list.")
        position = insert_after(db, after)
    item = PackingItem(list_id=list_id, position=position, **fields)
    db.add(item)
    db.flush()
    remember_item_labels(db, item)
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/api/packing-lists/{list_id}/items/bulk-create",
    response_model=list[PackingItemResponse],
    status_code=201,
)
def bulk_create(list_id: int, payload: PackingItemBulkCreate, db: Session = Depends(get_db)):
    """All or nothing: the body is validated whole before anything is written,
    and the rows are committed together.

    Placed one at a time in request order, each flushed before the next is
    placed, so two new items of the same new category land adjacent and in
    the order they were sent.
    """
    _get_list(db, list_id)

    items = []
    for fields in payload.items:
        position = place_in_group(db, list_id, fields.category)
        item = PackingItem(list_id=list_id, position=position, **fields.model_dump())
        db.add(item)
        db.flush()
        remember_item_labels(db, item)
        items.append(item)
    db.commit()
    for item in items:
        db.refresh(item)
    return items


@router.patch("/api/packing-items/{item_id}", response_model=PackingItemResponse)
def update(item_id: int, payload: PackingItemUpdate, db: Session = Depends(get_db)):
    item = _get(db, item_id)
    # `exclude_unset` rather than `exclude_none`: null is a legitimate value
    # here - clearing a category, or saying a quantity does not apply - and
    # excluding it would make those fields impossible to unset.
    changes = payload.model_dump(exclude_unset=True)
    moved = "category" in changes and changes["category"] != item.category
    for field, value in changes.items():
        setattr(item, field, value)
    # A new category is a new group, and the item joins the end of it rather
    # than staying where it was and splitting the sheet's blocks. A position
    # sent in the same PATCH is taken as meant and wins.
    if moved and "position" not in changes:
        item.position = place_in_group(db, item.list_id, item.category, exclude_id=item.id)
    # After the assignment, so a value typed into this PATCH is remembered
    # too - not only the ones an item was created with.
    remember_item_labels(db, item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/api/packing-items/{item_id}", status_code=204)
def delete(item_id: int, db: Session = Depends(get_db)):
    item = _get(db, item_id)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
