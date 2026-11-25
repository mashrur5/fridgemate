"""Standalone agent CLI (fridgemate-agent): tasks from a file, standard input or arguments, no server."""
import io

import pytest

from cli import agent_cli
from server.application.container import build_facade
from server.config import Config
from tests.conftest import TODAY
from tests.fakes import FakeLLMClient, FakeRecipeSource, recipe

ADD_EGGS = [{"tool": "propose_inventory_change",
             "args": {"op": "add", "name": "Eggs", "amount": 12, "unit": "pcs", "location": "fridge"}},
            {"final": {"reply": "Adding 12 eggs.", "question": None}}]


@pytest.fixture
def make():
    def _make(replies=()):
        llm = FakeLLMClient(list(replies))
        recipes = FakeRecipeSource([recipe("1", "Spinach Omelette", "French", ("spinach", 100, "g"), ("egg", 2, "pcs"))])
        return build_facade(Config(), llm=llm, recipes=recipes, in_memory=True, today=lambda: TODAY), llm
    return _make


def run(facade, argv, stdin=""):
    out = io.StringIO()
    code = agent_cli.main(argv, facade=facade, stdin=io.StringIO(stdin), stdout=out)
    return code, out.getvalue()


def test_runs_tasks_from_a_file(make, tmp_path):
    facade, llm = make(ADD_EGGS)
    task = tmp_path / "task.txt"
    task.write_text("# my tasks\n\nI bought 12 eggs\nadd Spinach 200 g\nlist\n", encoding="utf-8")
    code, out = run(facade, ["--input", str(task), "--trace"])
    assert code == 0
    assert "=== Task 1: I bought 12 eggs" in out and "Task 4" not in out  # comment and blank line skipped
    assert "Agent: Adding 12 eggs." in out and "Done: Add 12 pcs Eggs to the fridge" in out
    assert "propose_inventory_change" in out  # --trace shows the tool call
    assert "Added Spinach (200 g)" in out
    assert "Eggs" in out.split("=== Task 3: list")[1] and "Spinach" in out.split("=== Task 3: list")[1]
    assert "Done: 3 task(s), 0 failed" in out


def test_reads_standard_input_and_dry_run_changes_nothing(make):
    facade, _ = make(ADD_EGGS)
    code, out = run(facade, ["--input", "-", "--dry-run"], stdin="I bought 12 eggs\nlist\n")
    assert code == 0
    assert "Dry run: these changes were not applied." in out
    assert "The fridge is empty." in out


def test_piped_input_without_flags_and_tasks_as_arguments(make):
    facade, _ = make()
    assert "Added Milk (1 l)" in run(facade, [], stdin="add Milk 1 l\n")[1]
    assert "Milk" in run(facade, ["list"])[1]  # same local profile on the second run


def test_bad_tasks_are_reported_and_exit_code_is_1(make, tmp_path):
    facade, _ = make()
    code, out = run(facade, ["add Milk lots", "plan 30", "receipt nowhere.txt", "alerts"])
    assert code == 1
    assert "Error: use: add <name> <amount> <unit>" in out
    assert "Error: days must be between 3 and 5" in out
    assert "Error: receipt file not found" in out
    assert "Nothing is expiring soon." in out and "4 task(s), 3 failed" in out


def test_agent_unavailable_is_an_error_not_a_crash(make):
    facade, _ = make()  # no scripted replies: the fake LLM is unavailable
    code, out = run(facade, ["recipes 20"])
    assert code == 1 and "Error:" in out


def test_output_file_and_missing_input(make, tmp_path):
    facade, _ = make()
    result = tmp_path / "out.txt"
    run(facade, ["--output", str(result), "add Rice 2 kg"])
    assert "Added Rice (2 kg)" in result.read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="input file not found"):
        run(facade, ["--input", str(tmp_path / "missing.txt")])
