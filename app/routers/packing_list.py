"""Packing lists: the three shelves, creating one, and the cap that refuses.

The router owns wiring and status codes. What fills a slot, what eviction
destroys and what a copy carries all live in `app.services.domain.packing`.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import PackingList
from app.schemas.packing_list import (
    PackingListCreate,
    PackingListIndex,
    PackingListResponse,
    PackingListSummary,
    PackingListUpdate,
)
from app.services.domain.packing import (
    SLOT_CAP,
    copy_items,
    count_slots,
    evict,
    oldest_slot,
)

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
        f"You already have {SLOT_CAP} working lists. Creating another would "
        f"delete {names}, the oldest. Save it first if you want to keep it, or "
        f"confirm to replace it."
    )


def _make_room(db: Session, *, confirmed: bool) -> None:
    """Refuse, or evict, before a new working list is allowed to exist."""
    if count_slots(db) < SLOT_CAP:
        return
    slot = oldest_slot(db)
    if not confirmed:
        raise HTTPException(status_code=409, detail=_refusal(slot))
    evict(db, slot)


@router.get("", response_model=PackingListIndex)
def index(db: Session = Depends(get_db)):
    lists = (
        db.execute(
            select(PackingList)
            .options(selectinload(PackingList.items))
            .order_by(PackingList.created_at.desc(), PackingList.id.desc())
        )
        .scalars()
        .all()
    )

    # A list can be saved AND a template, so it appears on both shelves. It is
    # one row either way; the shelves are views of the flags, not categories.
    working = [
        packing_list
        for packing_list in lists
        if not packing_list.saved and not packing_list.template
    ]
    return PackingListIndex(
        recent=[PackingListSummary.model_validate(row) for row in working],
        saved=[PackingListSummary.model_validate(row) for row in lists if row.saved],
        templates=[
            PackingListSummary.model_validate(row) for row in lists if row.template
        ],
        evict_next=(
            [PackingListSummary.model_validate(row) for row in oldest_slot(db)]
            if count_slots(db) >= SLOT_CAP
            else []
        ),
    )


@router.post("", response_model=PackingListResponse, status_code=201)
def create(payload: PackingListCreate, db: Session = Depends(get_db)):
    source = None
    if payload.copy_from_id is not None:
        # Resolved before anything is destroyed. A copy from a list that does
        # not exist must not cost you the oldest one.
        source = db.get(PackingList, payload.copy_from_id)
        if source is None:
            raise HTTPException(status_code=404, detail="List to copy from not found.")

    if not payload.saved and not payload.template:
        _make_room(db, confirmed=payload.evict_confirmed)

    packing_list = PackingList(
        **payload.model_dump(exclude={"copy_from_id", "evict_confirmed"})
    )
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
        .options(selectinload(PackingList.items))
    ).scalar_one_or_none()
    if packing_list is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return packing_list


@router.patch("/{list_id}", response_model=PackingListResponse)
def update(list_id: int, payload: PackingListUpdate, db: Session = Depends(get_db)):
    packing_list = _get(db, list_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"evict_confirmed"})

    was_exempt = packing_list.saved or packing_list.template
    will_be_exempt = changes.get("saved", packing_list.saved) or changes.get(
        "template", packing_list.template
    )
    # Un-saving a list moves it back under the cap. Without this the cap is
    # enforceable only at creation, and saving then un-saving is a way to hold
    # five working lists with nothing complaining.
    if was_exempt and not will_be_exempt:
        _make_room(db, confirmed=payload.evict_confirmed)

    for field, value in changes.items():
        setattr(packing_list, field, value)

    db.commit()
    db.refresh(packing_list)
    return packing_list


@router.delete("/{list_id}", status_code=204)
def delete(list_id: int, db: Session = Depends(get_db)):
    packing_list = _get(db, list_id)
    db.delete(packing_list)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
