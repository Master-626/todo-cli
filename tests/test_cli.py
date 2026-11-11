import json
import os
import subprocess
import sys
from datetime import timedelta

import pytest
from click.testing import CliRunner

from todo_cli.cli import main
from todo_cli.models import TaskStore


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_add_tags_and_list_command(home):
    runner = CliRunner()
    result = runner.invoke(main, ["add", "Test", "-t", "work", "-t", "urgent"])
    assert result.exit_code == 0, result.output
    data = json.loads((home / ".todo-cli" / "tasks.json").read_text())
    assert data[0]["tags"] == ["work", "urgent"]
    assert runner.invoke(main, ["list"]).exit_code == 0


def test_separate_cli_processes_persist_all_operations(home):
    def run(*args):
        result = subprocess.run([sys.executable, "-m", "todo_cli.cli", *args],
                                text=True, capture_output=True, env=os.environ.copy())
        assert result.returncode == 0, result.stderr
        return result.stdout
    run("--help")
    run("--version")
    run("add", "Work", "-t", "work", "-p", "high")
    run("add", "Personal")
    assert "Work" in run("list", "-t", "work")
    run("done", "1")
    assert "Work" not in run("list")
    assert "Work" in run("list", "--all")
    run("delete", "2")
    assert "Completed: 1" in run("stats")
    assert TaskStore().get_stats() == {"total": 1, "completed": 1, "pending": 0,
                                     "by_priority": dict(low=0, medium=0, high=0, urgent=0)}


@pytest.mark.parametrize("command", [["done", "999"], ["delete", "999"]])
def test_missing_task_is_nonzero_without_typeerror(home, command):
    result = CliRunner().invoke(main, command)
    assert result.exit_code == 1
    assert "not found" in result.output
    assert "Traceback" not in result.output


def test_corrupt_cli_store_fails_without_success_or_overwrite(home):
    path = home / ".todo-cli" / "tasks.json"
    path.parent.mkdir()
    path.write_text("broken json")
    result = CliRunner().invoke(main, ["add", "Never saved"])
    assert result.exit_code == 1
    assert "Cannot read tasks" in result.output
    assert "Added task" not in result.output
    assert path.read_text() == "broken json"


def test_user_text_is_literal_and_does_not_fail_after_commit(home):
    runner = CliRunner()
    for command in (["add", "[/]", "-t", "[/]", "--due", "[/]"],
                    ["list"], ["done", "1"]):
        result = runner.invoke(main, command)
        assert result.exit_code == 0, result.exception
        assert "[/]" in result.output
    assert TaskStore().get_task(1).title == "[/]"


@pytest.mark.parametrize("encoding", ["ascii", "cp1252"])
def test_legacy_output_encoding_does_not_fail_after_save(home, encoding):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = encoding + ":strict"
    for args in (["add", "任务"], ["list"], ["done", "1"], ["stats"]):
        result = subprocess.run([sys.executable, "-m", "todo_cli.cli", *args],
                                capture_output=True, env=env)
        assert result.returncode == 0, result.stderr
        result.stdout.decode(encoding, errors="strict")
    assert TaskStore().get_task(1).title == "任务"
    assert TaskStore().get_task(1).done


def test_add_description_priority_and_due_date(home):
    result = CliRunner().invoke(
        main, ["add", "Write", "-d", "details", "-p", "low", "--due", "2026-12-01"]
    )
    assert result.exit_code == 0, result.output
    task = TaskStore().get_task(1)
    assert task.description == "details"
    assert task.priority == "low"
    assert task.due_date == "2026-12-01"


def test_empty_tag_filter_is_exact(home):
    runner = CliRunner()
    assert runner.invoke(main, ["add", "Blank", "-t", ""]).exit_code == 0
    assert runner.invoke(main, ["add", "Work", "-t", "work"]).exit_code == 0
    result = runner.invoke(main, ["list", "-t", ""])
    assert result.exit_code == 0, result.output
    assert "Blank" in result.output
    assert "Work" not in result.output


def test_list_rejects_unknown_priority(home):
    runner = CliRunner()
    assert runner.invoke(main, ["add", "Keep", "-p", "high"]).exit_code == 0
    result = runner.invoke(main, ["list", "-p", "HIGH"])
    text = result.output + (result.stderr or "")
    assert result.exit_code != 0
    assert "No tasks found" not in text
    assert "Keep" not in text
    listed = runner.invoke(main, ["list", "-p", "high"])
    assert listed.exit_code == 0, listed.output
    assert "Keep" in listed.output


def test_list_shows_full_task_id(home):
    path = home / ".todo-cli" / "tasks.json"
    path.parent.mkdir(parents=True)
    path.write_text('[{"id": 10000, "title": "Big"}]', encoding="utf-8")
    result = CliRunner().invoke(main, ["list"])
    assert result.exit_code == 0, result.output
    assert "10000" in result.output
    assert "Big" in result.output


def test_overdue_command_filters_pending_past_dates(home, frozen_today):
    yesterday = (frozen_today - timedelta(days=1)).isoformat()
    today = frozen_today.isoformat()
    tomorrow = (frozen_today + timedelta(days=1)).isoformat()
    runner = CliRunner()
    for args in (
        ["add", "Past", "--due", yesterday],
        ["add", "Today", "--due", today],
        ["add", "Future", "--due", tomorrow],
        ["add", "NoDue"],
        ["add", "OldDone", "--due", "2026-06-01"],
    ):
        assert runner.invoke(main, args).exit_code == 0
    assert runner.invoke(main, ["done", "5"]).exit_code == 0

    overdue = runner.invoke(main, ["list", "--overdue"])
    assert overdue.exit_code == 0, overdue.output
    assert "Overdue tasks" in overdue.output
    assert "Past" in overdue.output
    for title in ("Today", "Future", "NoDue", "OldDone"):
        assert title not in overdue.output

    listed = runner.invoke(main, ["list"])
    assert listed.exit_code == 0, listed.output
    for title in ("Past", "Today", "Future", "NoDue"):
        assert title in listed.output
    assert "OldDone" not in listed.output

    help_result = runner.invoke(main, ["list", "--help"])
    assert help_result.exit_code == 0
    assert "--overdue" in help_result.output
