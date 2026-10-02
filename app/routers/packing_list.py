"""Packing lists: the four shelves, creating one, and the queue that refuses.

The router owns wiring and status codes. What fills a 自動保存 slot, which
moves between kinds are allowed and what dropping a slot destroys live in
`app.services.domain.auto_save`; what a copy carries in
`app.services.domain.packing`.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constants import Kind, Status, Usage
from app.database import get_db
from app.models import PackingList
from app.schemas.packing_list import (
    PackingListCreate,
    PackingListIndex,
    PackingListResponse,
    PackingListSummary,
    PackingListUpdate,
)
from app.services.domain.auto_save import (
    AUTO_SAVE_LIMIT,
    AutoSaveFull,
    KindRefused,
    apply_kind,
    evict_next,
)
from app.services.domain.packing import copy_items, reset_list

router = APIRouter(prefix="/api/packing-lists", tags=["Packing lists"])

NOT_FOUND = "Packing list not found."


def _get(db: Session, list_id: int) -> PackingList:
    packing_list = db.get(PackingList, list_id)
    if packing_list is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return packing_list


def _refusal(slot: list[PackingList]) -> str:
    """The message a caller gets instead of a silently destroyed list.

    A plain string, because `detail` is a plain string in every media router
    and the frontend's fetch wrapper reads it as one. It names the lists so the
    refusal is actionable on its own; the ids the dialog needs come from
    `evict_next` on the index.
    """
    names = " and ".join(f'"{packing_list.name}"' for packing_list in slot)
    return (
        f"Auto-save already holds {AUTO_SAVE_LIMIT[PackingList]} lists. Marking "
        f"this one past would delete {names}, the oldest. Save it first if you "
        f"want to keep it, or confirm to replace it."
    )


def _summary(packing_list: PackingList) -> PackingListSummary:
    """A list plus the two numbers the index renders as a fraction."""
    summary = PackingListSummary.model_validate(packing_list)
    summary.item_count = len(packing_list.items)
    summary.settled_count = sum(
        1 for item in packing_list.items if item.status != Status.NOT_PACKED
    )
    return summary


@router.get("", response_model=PackingListIndex)
def index(db: Session = Depends(get_db)):
    lists = (
        db.execute(
            select(PackingList)
            .options(selectinload(PackingList.items), selectinload(PackingList.trip_leg))
            .order_by(PackingList.created_at.desc(), PackingList.id.desc())
        )
        .scalars()
        .all()
    )

    # Every list is on exactly one shelf: `kind` is one value, and 自動保存 is
    # the 一般 lists whose usage is past.
    def shelf(predicate) -> list[PackingListSummary]:
        return [_summary(row) for row in lists if predicate(row)]

    auto_saved = sorted(
        (row for row in lists if row.kind == Kind.FREE and row.usage == Usage.PAST),
        key=lambda row: (row.auto_saved_at, row.id),
        reverse=True,
    )
    return PackingListIndex(
        free=shelf(lambda row: row.kind == Kind.FREE and row.usage != Usage.PAST),
        auto_saved=[_summary(row) for row in auto_saved],
        saved=shelf(lambda row: row.kind == Kind.SAVED),
        templates=shelf(lambda row: row.kind == Kind.TEMPLATE),
        evict_next=[_summary(row) for row in evict_next(db, PackingList)],
    )


@router.post("", response_model=PackingListResponse, status_code=201)
def create(payload: PackingListCreate, db: Session = Depends(get_db)):
    source = None
    if payload.copy_from_id is not None:
        source = db.get(PackingList, payload.copy_from_id)
        if source is None:
            raise HTTPException(status_code=404, detail="List to copy from not found.")

    packing_list = PackingList(**payload.model_dump(exclude={"copy_from_id"}))
    db.add(packing_list)
    db.flush()

    if source is not None:
        copy_items(db, source, packing_list)

    db.commit()
    db.refresh(packing_list)
    return packing_list


@router.get("/{list_id}", response_model=PackingListResponse)
def read(list_id: int, db: Session = Depends(get_db)):
    packing_list = db.execute(
        select(PackingList)
        .where(PackingList.id == list_id)
        .options(selectinload(PackingList.items), selectinload(PackingList.trip_leg))
    ).scalar_one_or_none()
    if packing_list is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return packing_list


@router.patch("/{list_id}", response_model=PackingListResponse)
def update(list_id: int, payload: PackingListUpdate, db: Session = Depends(get_db)):
    packing_list = _get(db, list_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"evict_confirmed"})
    try:
        apply_kind(
            db,
            packing_list,
            changes,
            confirmed=payload.evict_confirmed,
            now=datetime.now(timezone.utc),
        )
    except KindRefused as refused:
        raise HTTPException(status_code=422, detail=str(refused)) from None
    except AutoSaveFull as full:
        raise HTTPException(status_code=409, detail=_refusal(full.slot)) from None

    for field, value in changes.items():
        setattr(packing_list, field, value)

    db.commit()
    db.refresh(packing_list)
    return packing_list


@router.post("/{list_id}/reset", response_model=PackingListResponse)
def reset(list_id: int, db: Session = Depends(get_db)):
    packing_list = _get(db, list_id)
    reset_list(db, packing_list)
    db.commit()
    db.expire_all()
    return read(list_id, db)


@router.delete("/{list_id}", status_code=204)
def delete(list_id: int, db: Session = Depends(get_db)):
    packing_list = _get(db, list_id)
    db.delete(packing_list)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
