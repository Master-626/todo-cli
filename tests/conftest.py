"""Shared fixtures. Task stores in these tests are disposable."""

from datetime import datetime

import pytest


@pytest.fixture
def frozen_today(monkeypatch):
    """Pin the store clock so overdue boundaries do not depend on the real day."""

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 15, 12, 0, 0)

    monkeypatch.setattr("todo_cli.models.datetime", FrozenDateTime)
    return datetime(2026, 6, 15).date()
