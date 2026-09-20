"""Every model, re-exported so `from app import models` reaches all of them.

Alembic's autogenerate reads `Base.metadata`, which is only populated for
modules that have actually been imported - so a model missing from this file
is a table missing from the next migration, with nothing to say so.
"""

from app.models.label_option import LabelOption
from app.models.packing_item import PackingItem
from app.models.packing_list import PackingList

__all__ = ["LabelOption", "PackingItem", "PackingList"]
