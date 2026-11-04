"""筆記: notes with links, kept in groups.

Groups follow the packing-list rule (`docs/business-rules.md`, "Groups"): a
new note joins the end of its group, a changed `group_name` moves the note to
the end of its new group, and a whole-order write that splits a group is
refused. The rule lives in `app.services.domain.ordering`.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Note, NoteLink
from app.schemas.note import NoteCreate, NoteOrder, NoteResponse, NoteUpdate
from app.services.domain.ordering import (
    OrderRefused,
    apply_order,
    check_groups,
    check_order,
    place_in_group,
    ungrouped_or_named,
)

router = APIRouter(tags=["Notes"])

NOTE_NOT_FOUND = "Note not found."

#: Every note is in one set: no scope narrows it.
ALL_NOTES: dict = {}


def _notes_query():
    return select(Note).options(selectinload(Note.links))


def _get_note(db: Session, note_id: int) -> Note:
    note = db.scalars(_notes_query().where(Note.id == note_id)).first()
    if note is None:
        raise HTTPException(status_code=404, detail=NOTE_NOT_FOUND)
    return note


def _link_rows(urls: list[str]) -> list[NoteLink]:
    return [NoteLink(url=url, position=position) for position, url in enumerate(urls)]


@router.get("/api/notes", response_model=list[NoteResponse])
def list_notes(db: Session = Depends(get_db)):
    return db.scalars(_notes_query().order_by(Note.position, Note.id)).all()


@router.put("/api/notes/order", response_model=list[NoteResponse])
def reorder_notes(payload: NoteOrder, db: Session = Depends(get_db)):
    """Every note's position in one write. A literal path, declared before the
    `{note_id}` routes, so "order" is never read as an id."""
    notes = {note.id: note for note in db.scalars(select(Note))}
    try:
        check_order(payload.note_ids, notes, noun="note", where="among the notes")
        check_groups(
            payload.note_ids,
            {note_id: note.group_name for note_id, note in notes.items()},
            noun="note",
            describe=ungrouped_or_named,
        )
    except OrderRefused as refused:
        raise HTTPException(status_code=422, detail=str(refused)) from None
    apply_order(notes, payload.note_ids)
    db.commit()
    db.expire_all()
    return list_notes(db)


@router.post("/api/notes", response_model=NoteResponse, status_code=201)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)):
    note = Note(
        group_name=payload.group_name,
        title=payload.title,
        description=payload.description,
        position=place_in_group(db, Note, ALL_NOTES, "group_name", payload.group_name),
        links=_link_rows(payload.links),
    )
    db.add(note)
    db.commit()
    db.expire_all()
    return _get_note(db, note.id)


@router.patch("/api/notes/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, payload: NoteUpdate, db: Session = Depends(get_db)):
    note = _get_note(db, note_id)
    changes = payload.model_dump(exclude_unset=True)
    if "links" in changes:
        # Replaced, not merged: delete-orphan removes the old rows.
        note.links = _link_rows(changes.pop("links"))
    moved = "group_name" in changes and changes["group_name"] != note.group_name
    for field, value in changes.items():
        setattr(note, field, value)
    if moved:
        note.position = place_in_group(
            db, Note, ALL_NOTES, "group_name", note.group_name, exclude_id=note.id
        )
    db.commit()
    db.expire_all()
    return _get_note(db, note_id)


@router.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db.delete(_get_note(db, note_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
