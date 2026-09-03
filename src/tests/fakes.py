"""Shared test fakes for DataTable-based local list."""

from textual.widgets import Label


class FakeDataTable:
    """Fake DataTable that mimics Textual's DataTable API for testing.

    Supports both old ListView-style (mount) and new DataTable-style (add_row) APIs.
    """

    def __init__(self):
        self.rows = {}  # key -> values tuple
        self.cursor_row = None
        self._row_keys = []  # ordered list of keys
        self.items = []  # backward compat with ListView tests

    def add_row(self, *values, key=None):
        if key is None:
            key = str(len(self._row_keys))
        self.rows[key] = values
        if key not in self._row_keys:
            self._row_keys.append(key)
        self.items.append(values)

    def clear(self):
        self.rows.clear()
        self._row_keys.clear()
        self.cursor_row = None
        self.items.clear()

    def update_cell(self, key, column, value):
        if key in self.rows:
            values = list(self.rows[key])
            if column < len(values):
                values[column] = value
            self.rows[key] = tuple(values)

    async def mount(self, *items):
        """Backward compat with ListView-style tests."""
        for item in items:
            if hasattr(item, 'data'):
                self.add_row(str(item.data), key=str(id(item.data)))
            else:
                self.add_row(str(item))

    def remove_children(self):
        self.clear()

    @property
    def children(self):
        return []

    def __len__(self):
        return len(self._row_keys)

    def __bool__(self):
        return True
