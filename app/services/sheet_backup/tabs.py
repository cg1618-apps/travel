"""The restore tabs: one per table, declared once, in restore order.

The backup writes these and the restore reads them, so the tab name, the model
and the order live here and nowhere else - media's `SheetTab` registry, for
the reason media gives: it used to keep the three in separate lists, and they
had drifted.

**The order is the restore order, and it is strict**: a row is inserted after
every row it points at, so each foreign key finds its target.

    Packing List     -> Packing Item          (packing_item.list_id)
    Transport Route  -> Transport Option      (transport_option.route_id)
    Transport Option -> Transport Departure   (transport_departure.option_id)
    Trip             -> Trip Leg              (trip_leg.trip_id)
    Packing List     -> Trip Leg              (trip_leg.packing_list_id)

Label Option points at nothing and comes first. Deleting runs the other way.
`tests/unit/test_sheet_backup_tabs.py` checks the order against the models'
own foreign keys and that every table is here.
"""

from dataclasses import dataclass

from sqlalchemy import Table

from app.models import (
    LabelOption,
    PackingItem,
    PackingList,
    TransportDeparture,
    TransportOption,
    TransportRoute,
    Trip,
    TripLeg,
)

#: The tab holding when the backup ran, the revision, and the row counts.
BACKUP_INFO = "Backup Info"


@dataclass(frozen=True)
class RestoreTab:
    name: str
    model: type

    @property
    def table(self) -> Table:
        return self.model.__table__


RESTORE_TABS: tuple[RestoreTab, ...] = (
    RestoreTab("Label Option", LabelOption),
    RestoreTab("Packing List", PackingList),
    RestoreTab("Packing Item", PackingItem),
    RestoreTab("Transport Route", TransportRoute),
    RestoreTab("Transport Option", TransportOption),
    RestoreTab("Transport Departure", TransportDeparture),
    RestoreTab("Trip", Trip),
    RestoreTab("Trip Leg", TripLeg),
)
