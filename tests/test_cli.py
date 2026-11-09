import json
import os
import subprocess
import sys

from click.testing import CliRunner
import pytest

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
