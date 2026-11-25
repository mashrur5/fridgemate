"""Standalone agent CLI: runs the Fridgemate agent straight from a terminal, with no server and no login.

    fridgemate-agent --llm gemini --input task.txt
    echo "I bought 6 eggs" | fridgemate-agent
    fridgemate-agent "what can I cook in 20 minutes?"

Each line of the input is one task. Lines that start with a keyword (add, list, alerts, recipes, find,
plan, shopping, receipt) run that feature; any other line is sent to the natural-language fridge agent (F12).
The objects are built through the same composition root and Facade the server uses, so the behaviour
is the same as in the GUI and the web CLI.
"""
from __future__ import annotations

import argparse
import mimetypes
import secrets
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable, Optional, TextIO

from server.agent.agent_trace import AgentTrace
from server.application.container import build_facade
from server.application.facade import FridgemateFacade, ItemInput
from server.application.request_context import RequestContext
from server.config import Config
from server.domain.errors import FridgemateError
from server.domain.model import RecipeRequest
from server.infrastructure.llm import LLMUnavailableError

LOCAL_EMAIL = "local-agent@fridgemate.local"
LOCAL_NAME = "Local user"
LOCAL_HOUSEHOLD = "My fridge"

KEYWORDS = """\
Task lines (one per line, # starts a comment):
  add <name> <amount> <unit>    add an item; AI picks the location and expiry (F01, F02, F04)
  list                          show the inventory (F01)
  alerts                        items that expire soon or have expired (F05)
  receipt <file>                read a receipt photo or .txt file and add its items (F03)
  recipes [minutes]             recipe agent on what is in the fridge (F07, F08)
  find <a, b, c>                recipes for the ingredients you list (F10)
  plan [days]                   waste-rescue meal plan, 3 to 5 days (F13)
  shopping                      show the shopping list (F11)
  anything else                 natural-language fridge agent, e.g. "I used 2 eggs" (F12)
"""


def _qty(q) -> str:
    return f"{q.amount:g} {q.unit}" if q is not None else ""


class AgentRunner:
    """Runs one task line at a time against the Facade and prints the result."""

    def __init__(self, facade: FridgemateFacade, ctx: RequestContext, out: TextIO, *,
                 apply: bool = True, show_trace: bool = False, base_dir: Path = Path(".")) -> None:
        self.facade, self.ctx, self.out = facade, ctx, out
        self.apply, self.show_trace, self.base_dir = apply, show_trace, base_dir
        self.handlers: dict[str, Callable[[str], None]] = {
            "add": self.add, "list": self.list, "alerts": self.alerts, "receipt": self.receipt,
            "recipes": self.recipes, "find": self.find, "plan": self.plan, "shopping": self.shopping,
        }

    def say(self, text: str = "") -> None:
        print(text, file=self.out)

    def run(self, tasks: Iterable[str]) -> int:
        """Runs every task. Returns how many tasks failed."""
        failed = number = 0
        for raw in tasks:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            number += 1
            self.say(f"\n=== Task {number}: {line}")
            try:
                self.run_task(line)
            except (FridgemateError, ValueError, LLMUnavailableError, OSError) as e:
                failed += 1
                self.say(f"Error: {e}")
        if number == 0:
            self.say("No tasks found. " + KEYWORDS.splitlines()[0])
        usage = self.facade.ai_status()
        self.say(f"\nDone: {number} task(s), {failed} failed. AI ({usage['provider']}): {usage['calls']} call(s), "
                 f"{usage['input_tokens']} input and {usage['output_tokens']} output tokens.")
        return failed

    def run_task(self, line: str) -> None:
        word, _, rest = line.partition(" ")
        handler = self.handlers.get(word.lower())
        if handler is None:
            self.ask(line)
        else:
            handler(rest.strip())

    # ---------- task handlers ----------

    def add(self, args: str) -> None:
        parts = args.split()
        if len(parts) < 3:
            raise ValueError("use: add <name> <amount> <unit>, e.g. add Milk 1 l")
        name, amount, unit = " ".join(parts[:-2]), parts[-2], parts[-1]
        try:
            value = float(amount)
        except ValueError:
            raise ValueError(f"'{amount}' is not a number") from None
        data = ItemInput(name, value, unit)
        result = self.facade.add_item(self.ctx, data) if self.apply else self.facade.build_item(self.ctx, data)
        item = result.item
        self.say(("Added " if self.apply else "Would add ") +
                 f"{item.name} ({_qty(item.quantity)}) to the {item.location.value}, expires {item.expiry_date}.")
        for note in (result.location_note, result.expiry_note):
            if note:
                self.say(f"  - {note}")

    def list(self, _: str = "") -> None:
        items = self.facade.list_items(self.ctx)
        if not items:
            self.say("The fridge is empty.")
        for item in sorted(items, key=lambda i: (i.location.value, i.expiry_date)):
            self.say(f"  {item.location.value:<8} {item.name:<20} {_qty(item.quantity):<10} "
                     f"expires {item.expiry_date} ({item.freshness_label()})")

    def alerts(self, _: str = "") -> None:
        items = self.facade.get_alerts(self.ctx)
        if not items:
            self.say("Nothing is expiring soon.")
        for item in items:
            self.say(f"  {item.freshness_label():<14} {item.name} ({_qty(item.quantity)}), expires {item.expiry_date}")

    def receipt(self, args: str) -> None:
        if not args:
            raise ValueError("use: receipt <file>, a photo (jpg/png) or a .txt file")
        path = Path(args).expanduser()
        if not path.is_absolute() and not path.exists():
            path = self.base_dir / path
        if not path.is_file():
            raise ValueError(f"receipt file not found: {args}")
        if path.suffix.lower() == ".txt":
            drafts = self.facade.parse_receipt_text(self.ctx, path.read_text(encoding="utf-8"))
        else:
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            drafts = self.facade.parse_receipt_image(self.ctx, path.read_bytes(), mime)
        if not drafts:
            self.say("No grocery items were found on this receipt.")
            return
        for d in drafts:
            price = f", ${d.item.price}" if d.item.price is not None else ""
            self.say(f"  {d.item.name} ({_qty(d.item.quantity)}{price}) -> {d.item.location.value}, "
                     f"expires {d.item.expiry_date}" + (f"  [{d.location_note}]" if d.location_note else ""))
        if self.apply:
            inputs = [ItemInput(d.item.name, d.item.quantity.amount, d.item.quantity.unit, d.item.location.value,
                                d.item.expiry_date, price=d.item.price) for d in drafts]
            saved = self.facade.save_receipt(self.ctx, inputs, self.ctx.member.id)
            self.say(f"Saved {len(saved)} item(s).")
        else:
            self.say("Dry run: nothing was saved.")

    def recipes(self, args: str) -> None:
        minutes = self._int(args, "minutes", 5, 300) if args else None
        result = self.facade.suggest_recipes(self.ctx, RecipeRequest(max_minutes=minutes))
        self._print_recipes(result)

    def find(self, args: str) -> None:
        names = [n.strip() for n in args.split(",") if n.strip()]
        if not names:
            raise ValueError("use: find <ingredient, ingredient, ...>")
        self._print_recipes(self.facade.find_recipes(self.ctx, names, RecipeRequest()))

    def plan(self, args: str) -> None:
        days = self._int(args, "days", 3, 5) if args else 3
        plan = self.facade.plan_meals(self.ctx, days)
        for meal in plan.meals:
            if meal.suggestion is None:
                self.say(f"  {meal.day}: no meal ({meal.note})" if meal.note else f"  {meal.day}: no meal")
                continue
            uses = ", ".join(c.item_name or c.ingredient.name for c in meal.suggestion.used if c.expiring)
            self.say(f"  {meal.day}: {meal.suggestion.recipe.name}" + (f" (uses up {uses})" if uses else ""))
        for note in plan.notes:
            self.say(f"  Note: {note}")
        self._print_trace(self.facade.meal_planner.last_trace)

    def shopping(self, _: str = "") -> None:
        items = self.facade.get_shopping_list(self.ctx).items
        if not items:
            self.say("The shopping list is empty.")
        for item in items:
            self.say(f"  [{'x' if item.checked else ' '}] {item.name} {_qty(item.quantity)}".rstrip())

    def ask(self, message: str) -> None:
        reply = self.facade.chat(self.ctx, message)
        self.say(f"Agent: {reply.reply}")
        if reply.question:
            self.say(f"Agent asks: {reply.question}")
        changes = reply.proposal.changes
        for change in changes:
            self.say(f"  - {change.describe()}")
        if changes and self.apply:
            for line in self.facade.confirm_changes(self.ctx, reply.proposal.id):
                self.say(f"  Done: {line}")
        elif changes:
            self.facade.cancel_changes(self.ctx, reply.proposal.id)
            self.say("  Dry run: these changes were not applied.")
        self._print_trace(reply.trace)

    # ---------- helpers ----------

    def _print_recipes(self, result) -> None:
        if result.choices:
            self.say(f"Agent: {result.choices}")
        if not result.suggestions:
            self.say("No recipes found.")
        for n, s in enumerate(result.suggestions, 1):
            source = "AI-written" if s.recipe.ai_generated else f"TheMealDB #{s.recipe.id}"
            time = f", about {s.estimated_minutes} min" if s.estimated_minutes else ""
            self.say(f"{n}. {s.recipe.name} ({source}{time})")
            if s.explanation:
                self.say(f"   Why: {s.explanation}")
            if s.used:
                self.say("   Uses: " + ", ".join(c.item_name or c.ingredient.name for c in s.used))
            for c in s.missing:
                sub = f" (or use {c.substitute})" if c.substitute else ""
                self.say(f"   Missing: {c.ingredient.name} {_qty(c.ingredient.quantity)}".rstrip() + sub)
        for note in result.notes:
            self.say(f"Note: {note}")
        self._print_trace(result.trace)

    def _print_trace(self, trace: Optional[AgentTrace]) -> None:
        if not (self.show_trace and trace):
            return
        self.say(f"  Trace ({trace.agent}):")
        for step in trace.steps:
            self.say(f"    {step.kind:<6} {step.tool or '':<22} {step.detail[:160]}")

    @staticmethod
    def _int(text: str, what: str, low: int, high: int) -> int:
        try:
            value = int(text.split()[0])
        except ValueError:
            raise ValueError(f"{what} must be a whole number") from None
        if not low <= value <= high:
            raise ValueError(f"{what} must be between {low} and {high}")
        return value


def local_context(facade: FridgemateFacade) -> RequestContext:
    """The standalone CLI has no login: it uses one local profile, created on first run."""
    member = facade.members.find_by_account(LOCAL_EMAIL)
    if member is None:
        member = facade.register(LOCAL_EMAIL, secrets.token_urlsafe(24), LOCAL_NAME)
    if member.household_id is None:
        household = facade.create_household(member, LOCAL_HOUSEHOLD)
    else:
        household = facade.households.households.find_by_id(member.household_id)
    return RequestContext(member, household)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fridgemate-agent", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Run the Fridgemate agent from a terminal on tasks from a file, standard input or the "
                    "command line. No server or login is needed.",
        epilog=KEYWORDS + "\nExamples:\n  fridgemate-agent --llm gemini --input examples/task.txt\n"
                          "  echo \"I bought 6 eggs\" | fridgemate-agent\n"
                          "  fridgemate-agent --dry-run \"I finished the milk\"")
    p.add_argument("tasks", nargs="*", help="task lines to run (used when --input is not given)")
    p.add_argument("-i", "--input", metavar="FILE",
                   help="file with one task per line; '-' reads standard input")
    p.add_argument("-o", "--output", metavar="FILE", help="also write the results to this file")
    p.add_argument("--llm", choices=["gemini", "ollama", "none"],
                   help="LLM to use (default: LLM_PROVIDER from .env, else gemini); none = rule fallbacks only")
    p.add_argument("--model", help="model name for the chosen LLM (default: from .env)")
    p.add_argument("--db", metavar="PATH", help="SQLite database file (default: DATABASE_PATH from .env)")
    p.add_argument("--memory", action="store_true", help="use a fresh in-memory database (nothing is saved)")
    p.add_argument("--dry-run", action="store_true", help="show proposed changes without applying them")
    p.add_argument("--trace", action="store_true", help="print each agent step (tool calls and answers)")
    return p


def read_tasks(args: argparse.Namespace, stdin: TextIO) -> tuple[list[str], Path]:
    if args.input == "-":
        return stdin.read().splitlines(), Path(".")
    if args.input:
        path = Path(args.input).expanduser()
        if not path.is_file():
            raise SystemExit(f"fridgemate-agent: input file not found: {args.input}")
        return path.read_text(encoding="utf-8").splitlines(), path.parent
    if args.tasks:
        return list(args.tasks), Path(".")
    if not stdin.isatty():
        return stdin.read().splitlines(), Path(".")
    raise SystemExit("fridgemate-agent: give a task, --input FILE, or pipe tasks into standard input "
                     "(see --help)")


class _Tee:
    def __init__(self, *streams: TextIO) -> None:
        self.streams = streams

    def write(self, text: str) -> None:
        for s in self.streams:
            s.write(text)

    def flush(self) -> None:
        for s in self.streams:
            s.flush()


def main(argv: Optional[list[str]] = None, *, facade: Optional[FridgemateFacade] = None,
         stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    args = build_parser().parse_args(argv)
    tasks, base_dir = read_tasks(args, stdin)

    if facade is None:
        config = Config.from_env()
        if args.llm:
            config = replace(config, llm_provider=args.llm)
        if args.model:
            field = "ollama_model" if config.llm_provider == "ollama" else "gemini_model"
            config = replace(config, **{field: args.model})
        if args.db:
            config = replace(config, database_path=args.db)
        facade = build_facade(config, in_memory=args.memory)

    out_file = open(args.output, "w", encoding="utf-8") if args.output else None
    try:
        out = _Tee(stdout, out_file) if out_file else stdout
        runner = AgentRunner(facade, local_context(facade), out, apply=not args.dry_run,
                             show_trace=args.trace, base_dir=base_dir)
        failed = runner.run(tasks)
    finally:
        if out_file:
            out_file.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
