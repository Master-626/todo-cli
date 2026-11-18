from datetime import timedelta

import pytest

from todo_cli.models import TaskStore


def test_add_task(tmp_path):
    """Test adding a task."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    task = store.add_task("Test task", priority="high", tags=["work", "urgent"])
    assert task.id == 1
    assert task.title == "Test task"
    assert task.priority == "high"
    assert "work" in task.tags


def test_list_tasks(tmp_path):
    """Test listing tasks."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    store.add_task("Task 1")
    store.add_task("Task 2")
    store.add_task("Task 3", priority="high")

    all_tasks = store.list_tasks()
    assert len(all_tasks) == 3

    high_priority = store.list_tasks(priority="high")
    assert len(high_priority) == 1


def test_complete_task(tmp_path):
    """Test completing a task."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    task = store.add_task("Test task")

    completed = store.complete_task(task.id)
    assert completed.done is True
    assert completed.completed_at is not None


def test_delete_task(tmp_path):
    """Test deleting a task."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    task = store.add_task("Test task")

    assert store.delete_task(task.id) is True
    assert store.get_task(task.id) is None


def test_task_stats(tmp_path):
    """Test task statistics."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    store.add_task("Task 1", priority="high")
    store.add_task("Task 2", priority="medium")
    task3 = store.add_task("Task 3", priority="low")
    store.complete_task(task3.id)

    stats = store.get_stats()
    assert stats["total"] == 3
    assert stats["completed"] == 1
    assert stats["pending"] == 2
    assert stats["by_priority"] == {"low": 0, "medium": 1, "high": 1, "urgent": 0}


def test_created_at_round_trip(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    task = store.add_task("A")
    assert task.created_at
    assert store.get_task(task.id).created_at == task.created_at
    store.complete_task(task.id)
    assert store.get_task(task.id).created_at == task.created_at
    assert store.get_task(task.id).completed_at


def test_blank_title_and_unknown_priority_are_rejected(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    with pytest.raises(ValueError, match="title"):
        store.add_task("   ")
    with pytest.raises(ValueError, match="priority"):
        store.add_task("Nope", priority="nope")
    assert store.list_tasks() == []
    assert not store.file_path.exists()


def test_filters_treat_only_none_as_unset(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    store.add_task("Blank", tags=[""])
    store.complete_task(1)
    store.add_task("Work", priority="high", tags=["work"])

    assert [task.title for task in store.list_tasks()] == ["Blank", "Work"]
    assert [task.title for task in store.list_tasks(include_done=False)] == ["Work"]
    assert [task.title for task in store.list_tasks(tag="")] == ["Blank"]
    assert [task.title for task in store.list_tasks(priority="")] == []
    assert [task.title for task in store.list_tasks(priority="high", tag="work")] == ["Work"]


def test_non_integer_ids_do_not_select_tasks(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    keep = store.add_task("Keep")
    other = store.add_task("Other")
    before = store.file_path.read_bytes()
    for bad in (True, False, 1.0, 2.0, "1"):
        with pytest.raises(ValueError, match="integer"):
            store.get_task(bad)
        with pytest.raises(ValueError, match="integer"):
            store.complete_task(bad)
        with pytest.raises(ValueError, match="integer"):
            store.delete_task(bad)
        with pytest.raises(ValueError, match="integer"):
            store.update_task(bad, title="Changed")
    assert store.file_path.read_bytes() == before
    assert [(task.id, task.title, task.done) for task in store.list_tasks()] == [
        (keep.id, "Keep", False),
        (other.id, "Other", False),
    ]


def test_overdue_uses_canonical_dates_and_skips_completed(tmp_path, frozen_today):
    store = TaskStore(str(tmp_path / "tasks.json"))
    yesterday = (frozen_today - timedelta(days=1)).isoformat()
    today = frozen_today.isoformat()
    tomorrow = (frozen_today + timedelta(days=1)).isoformat()
    store.add_task("Yesterday", due_date=yesterday, priority="high", tags=["tax"])
    store.add_task("Today", due_date=today, priority="high", tags=["tax"])
    store.add_task("Tomorrow", due_date=tomorrow)
    store.add_task("Undated")
    store.add_task("Markup", due_date="[/]")
    store.add_task("Invalid", due_date="2026-02-31")
    store.add_task("Unpadded", due_date="{}-{}-{}".format(frozen_today.year, frozen_today.month, 1))
    store.add_task("Leap", due_date="2024-02-29", priority="low")
    done = store.add_task("Finished", due_date="2026-06-01", priority="high", tags=["tax"])
    store.complete_task(done.id)
    store.add_task("Other", due_date="2026-06-10", priority="high", tags=["home"])

    assert [task.title for task in store.list_tasks(overdue=True)] == ["Yesterday", "Leap", "Other"]
    assert "Finished" in [task.title for task in store.list_tasks()]
    assert [task.title for task in store.list_tasks(overdue=True, priority="high", tag="tax")] == [
        "Yesterday"
    ]
    assert "Finished" not in [task.title for task in store.list_tasks(include_done=True, overdue=True)]
