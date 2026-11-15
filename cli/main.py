"""FridgemateCLI: the command-line interface (typer). Every command calls the API through FridgemateClient.

Run `python -m cli --help` (or `fridgemate --help` after `pip install -e .`)."""
from __future__ import annotations

import mimetypes
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.client import ApiError, FridgemateClient

app = typer.Typer(help="Fridgemate: shared-fridge assistant for roommates.", no_args_is_help=True,
                  pretty_exceptions_enable=False)
household_app = typer.Typer(help="F06: create, join or show your household.", no_args_is_help=True)
prefs_app = typer.Typer(help="F06: dietary restrictions and dislikes.", no_args_is_help=True)
items_app = typer.Typer(help="F01/F02/F04: manage inventory items.", no_args_is_help=True)
receipt_app = typer.Typer(help="F03: import a grocery receipt.", no_args_is_help=True)
recipes_app = typer.Typer(help="F07/F08/F10: recipe suggestions.", no_args_is_help=True)
shopping_app = typer.Typer(help="F11: shopping list.", no_args_is_help=True)
plan_app = typer.Typer(help="F13: waste-rescue meal plan.", invoke_without_command=True)
costs_app = typer.Typer(help="F14: shared cost split.", invoke_without_command=True)
for sub, name in [(household_app, "household"), (prefs_app, "prefs"), (items_app, "items"), (receipt_app, "receipt"),
                  (recipes_app, "recipes"), (shopping_app, "shopping"), (plan_app, "plan"), (costs_app, "costs")]:
    app.add_typer(sub, name=name)

console = Console()
client = FridgemateClient()


def fail(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ApiError as e:
        fail(str(e))


def qty(q: Optional[dict]) -> str:
    return f"{q['amount']:g} {q['unit']}" if q else ""


FRESH_COLOR = {"Fresh": "green", "Expiring soon": "yellow", "Expired": "red"}


def show_items(items: list[dict], title: str = "Inventory") -> None:
    if not items:
        console.print("[dim]No items.[/dim]")
        return
    t = Table(title=title)
    for col in ("ID", "Name", "Qty", "Where", "Owner", "Expires", "Freshness"):
        t.add_column(col)
    for i in items:
        color = FRESH_COLOR.get(i["freshness"], "white")
        owner = i["owner"] + (f" (offered by {i['offered_by']})" if i["is_offered"] else "")
        expires = i["expiry_date"] + (" (est.)" if i["expiry_estimated"] else "")
        t.add_row(i["id"][:8], i["name"] + (" [low]" if i["is_low"] else ""), qty(i["quantity"]),
                  i["location"], owner, expires, f"[{color}]{i['freshness']}[/{color}]")
    console.print(t)


def find_item(ref: str) -> dict:
    """Accept an id prefix (from `items list`) or a name."""
    items = call(client.get, "/api/items")["items"]
    by_id = [i for i in items if i["id"].startswith(ref.lower())]
    if len(by_id) == 1:
        return by_id[0]
    by_name = [i for i in items if i["name"].lower() == ref.lower()] or \
              [i for i in items if ref.lower() in i["name"].lower()]
    if len(by_name) == 1:
        return by_name[0]
    if not by_name:
        fail(f"no item matches '{ref}'")
    fail(f"'{ref}' matches several items: " + ", ".join(f"{i['name']} ({i['id'][:8]})" for i in by_name))


# ---------------- accounts (UC16) ----------------

@app.command()
def register(email: str = typer.Option(..., prompt=True), name: str = typer.Option(..., prompt="Your name"),
             password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True)):
    """Create an account."""
    r = call(client.post, "/api/account/register", {"email": email, "password": password, "name": name}, auth=False)
    client.store.save(r["token"])
    console.print(f"Welcome, {r['member']['name']}! Next: [bold]fridgemate household create \"Name\"[/bold] "
                  "or [bold]fridgemate household join CODE[/bold]")


@app.command()
def login(email: str = typer.Option(..., prompt=True),
          password: str = typer.Option(..., prompt=True, hide_input=True)):
    """Log in (the token is saved in ~/.fridgemate)."""
    r = call(client.post, "/api/account/login", {"email": email, "password": password}, auth=False)
    client.store.save(r["token"])
    console.print("[green]Logged in.[/green]")


@app.command()
def logout():
    """Log out."""
    try:
        client.post("/api/account/logout")
    except ApiError:
        pass
    client.store.clear()
    console.print("Logged out.")


@app.command("change-password")
def change_password(old: str = typer.Option(..., prompt="Current password", hide_input=True),
                    new: str = typer.Option(..., prompt="New password", hide_input=True, confirmation_prompt=True)):
    """Change your password."""
    call(client.post, "/api/account/password", {"old_password": old, "new_password": new})
    console.print("[green]Password changed.[/green]")


@app.command()
def whoami():
    """Show who is logged in, the household and AI status."""
    r = call(client.get, "/api/account/me")
    m, h, ai = r["member"], r["household"], r["ai"]
    console.print(f"{m['name']} <{m['email']}>")
    console.print(f"Household: {h['name']} (invite code {h['invite_code']})" if h else "No household yet.")
    console.print(f"AI: {ai['provider']}, {ai['calls']} calls this server session, "
                  f"{ai['input_tokens'] + ai['output_tokens']} tokens")


# ---------------- F06 household ----------------

@household_app.command("create")
def household_create(name: str):
    """Create a household and get an invite code."""
    h = call(client.post, "/api/household", {"name": name})
    console.print(f"Created [bold]{h['name']}[/bold]. Invite code: [bold cyan]{h['invite_code']}[/bold cyan]")


@household_app.command("join")
def household_join(invite_code: str):
    """Join a roommate's household with their invite code."""
    h = call(client.post, "/api/household/join", {"invite_code": invite_code})
    console.print(f"Joined [bold]{h['name']}[/bold] with {len(h['members'])} member(s).")


@household_app.command("show")
def household_show():
    """Members and invite code."""
    h = call(client.get, "/api/household")
    console.print(f"[bold]{h['name']}[/bold]  invite code: [cyan]{h['invite_code']}[/cyan]")
    for m in h["members"]:
        console.print(f"  - {m['name']}  ({m['id'][:8]})")


@prefs_app.command("set")
def prefs_set(restrict: list[str] = typer.Option([], "--restrict", "-r",
                                                 help="vegetarian, vegan, halal, gluten-free, dairy-free, nut-free"),
              dislike: list[str] = typer.Option([], "--dislike", "-d", help="an ingredient you don't eat")):
    """Save your preferences (replaces the old ones). Every AI feature respects them."""
    m = call(client.put, "/api/household/preferences",
             {"dietary_restrictions": restrict, "disliked_ingredients": dislike})
    console.print(f"Restrictions: {', '.join(m['dietary_restrictions']) or 'none'}; "
                  f"dislikes: {', '.join(m['disliked_ingredients']) or 'none'}")


@prefs_app.command("show")
def prefs_show():
    m = call(client.get, "/api/account/me")["member"]
    console.print(f"Restrictions: {', '.join(m['dietary_restrictions']) or 'none'}; "
                  f"dislikes: {', '.join(m['disliked_ingredients']) or 'none'}")


# ---------------- F01 / F02 / F04 items ----------------

@items_app.command("list")
def items_list(location: Optional[str] = typer.Option(None, help="fridge, freezer or pantry"),
               owner: Optional[str] = typer.Option(None, help="me, shared or offered"),
               fresh: Optional[str] = typer.Option(None, help="'Fresh', 'Expiring soon' or 'Expired'"),
               search: Optional[str] = typer.Option(None, "--search", "-s")):
    """List your items, Shared items and roommates' offers."""
    r = call(client.get, "/api/items", params={k: v for k, v in
                                               {"location": location, "owner": owner, "freshness": fresh, "q": search}.items() if v})
    show_items(r["items"])


@items_app.command("add")
def items_add(name: str, amount: float, unit: str = typer.Argument(..., help="g, kg, ml, l or pcs"),
              location: Optional[str] = typer.Option(None, help="leave out to let the AI suggest (F02)"),
              expiry: Optional[str] = typer.Option(None, help="YYYY-MM-DD; leave out to estimate (F04)"),
              shared: bool = typer.Option(False, "--shared", help="owned by the whole household"),
              price: Optional[float] = None, paid_by_me: bool = typer.Option(False, "--paid-by-me")):
    """Add an item. Missing location and expiry are filled in by the AI (rule table if the AI is down)."""
    body = {"name": name, "amount": amount, "unit": unit, "location": location, "expiry_date": expiry,
            "owner": "shared" if shared else "me", "price": price}
    if paid_by_me:
        body["payer_id"] = call(client.get, "/api/account/me")["member"]["id"]
    r = call(client.post, "/api/items", body)
    i = r["item"]
    console.print(f"[green]Added[/green] {i['name']} ({qty(i['quantity'])}) to the {i['location']}, "
                  f"expires {i['expiry_date']}.")
    for note in (r["location_note"], r["expiry_note"]):
        if note:
            console.print(f"  [cyan]{note}[/cyan]")
    console.print("  Undo with: fridgemate undo")


@items_app.command("edit")
def items_edit(item: str, amount: Optional[float] = None, unit: Optional[str] = None,
               location: Optional[str] = None, expiry: Optional[str] = None, name: Optional[str] = None,
               shared: Optional[bool] = typer.Option(None, "--shared/--mine")):
    """Edit an item (by id prefix or name)."""
    target = find_item(item)
    body = {k: v for k, v in {"amount": amount, "unit": unit, "location": location, "expiry_date": expiry,
                              "name": name}.items() if v is not None}
    if shared is not None:
        body["owner"] = "shared" if shared else "me"
    i = call(client.patch, f"/api/items/{target['id']}", body)
    console.print(f"[green]Updated[/green] {i['name']}: {qty(i['quantity'])}, {i['location']}, expires {i['expiry_date']}")


@items_app.command("remove")
def items_remove(item: str):
    """Remove an item (by id prefix or name)."""
    target = find_item(item)
    call(client.delete, f"/api/items/{target['id']}")
    console.print(f"Removed {target['name']}. Undo with: fridgemate undo")


@items_app.command("suggest")
def items_suggest(name: str):
    """F02 + F04: where to store an item and how long it lasts."""
    r = call(client.get, "/api/items/suggest", params={"name": name})
    console.print(f"{r['location'].title()}: {r['reason']} [dim]({r['location_source']})[/dim]")
    console.print(f"Estimated expiry: {r['expiry_date']} [dim]({r['expiry_source']})[/dim]")


@app.command()
def undo():
    """Undo your last inventory change."""
    console.print(call(client.post, "/api/items/undo")["message"])


# ---------------- F05 alerts, F15 offers ----------------

@app.command()
def alerts():
    """F05: items expiring in the next 3 days, then expired items."""
    r = call(client.get, "/api/items/alerts")
    if r["banner"]:
        console.print(Panel(r["banner"], style="yellow"))
    else:
        console.print("Nothing is expiring soon.")
    if r["expiring"]:
        show_items(r["expiring"], "Use it first")
    if r["expired"]:
        show_items(r["expired"], "Expired (remove these)")


@app.command()
def offer(item: str, note: str = typer.Option("", help='e.g. "half a bag left"')):
    """F15: offer one of your expiring items to your roommates."""
    target = find_item(item)
    i = call(client.post, f"/api/items/{target['id']}/offer", {"note": note})
    console.print(f"Offered {i['name']} to the household. Undo with: fridgemate undo")


@app.command()
def claim(item: str):
    """F15: claim an item a roommate offered (first claim wins)."""
    target = find_item(item)
    i = call(client.post, f"/api/items/{target['id']}/claim")
    console.print(f"[green]You claimed {i['name']}.[/green] It's yours now.")


@app.command()
def notifications():
    """F15: offers and claims from your roommates."""
    r = call(client.get, "/api/notifications")
    if not r["notifications"]:
        console.print("No notifications.")
    for n in r["notifications"]:
        console.print(f"{'[bold]*[/bold] ' if not n['read'] else '  '}{n['created_at']}  {n['message']}")
    call(client.post, "/api/notifications/read")


# ---------------- F03 receipts ----------------

@receipt_app.command("import")
def receipt_import(path: Path = typer.Argument(..., exists=True, help="receipt photo (jpg/png) or a .txt file")):
    """Read a receipt with the AI, review every item, then save."""
    if path.suffix.lower() == ".txt":
        r = call(client.post, "/api/receipts/parse-text", {"text": path.read_text(encoding="utf-8")})
    else:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        r = call(client.post, "/api/receipts/parse", files={"photo": (path.name, path.read_bytes(), mime)})
    drafts = r["items"]
    if not drafts:
        fail("no food items were found on the receipt")
    me = call(client.get, "/api/account/me")
    members = me["household"]["members"]
    t = Table(title="Receipt items (nothing is saved yet)")
    for col in ("#", "Name", "Qty", "Price", "Where", "Expires", "Note"):
        t.add_column(col)
    for n, d in enumerate(drafts, 1):
        t.add_row(str(n), d["name"], qty(d["quantity"]), d["price"] or "", d["location"], d["expiry_date"], d["note"])
    console.print(t)
    remove = typer.prompt("Numbers to remove (e.g. 2,5) or Enter to keep all", default="", show_default=False)
    drop = {int(x) for x in remove.replace(" ", "").split(",") if x.isdigit()}
    owners = ", ".join(["me", "shared"] + [m["name"] for m in members if m["id"] != me["member"]["id"]])
    keep = []
    for n, d in enumerate(drafts, 1):
        if n in drop:
            continue
        who = typer.prompt(f"Owner of {d['name']} ({owners})", default="me")
        owner = "shared" if who.lower() == "shared" else "me"
        match = next((m for m in members if m["name"].lower() == who.lower() and m["id"] != me["member"]["id"]), None)
        if match:
            owner = match["id"]
        keep.append({"name": d["name"], "amount": d["quantity"]["amount"], "unit": d["quantity"]["unit"],
                     "location": d["location"], "expiry_date": d["expiry_date"], "owner": owner, "price": d["price"]})
    if not keep:
        console.print("Everything was removed, nothing saved.")
        return
    payer = None
    if typer.confirm("Did you pay for this receipt?", default=True):
        payer = me["member"]["id"]
    if not typer.confirm(f"Save {len(keep)} item(s)?", default=True):
        console.print("Closed without saving.")
        return
    console.print(f"[green]{call(client.post, '/api/receipts/save', {'items': keep, 'payer_id': payer})['message']}[/green]")


# ---------------- F07 / F08 / F10 recipes, F09 cook ----------------

def show_recipes(r: dict, can_cook: bool) -> None:
    for note in r["notes"]:
        console.print(f"[yellow]{note}[/yellow]")
    if r.get("choices"):
        console.print(f"[cyan]AI choices:[/cyan] {r['choices']}")
    for n, s in enumerate(r["suggestions"], 1):
        rec = s["recipe"]
        head = f"{n}. {rec['name']}" + (" [magenta](AI-generated)[/magenta]" if rec["ai_generated"] else "")
        meta = ", ".join(x for x in [rec["cuisine"], f"~{s['estimated_minutes']} min (est.)" if s["estimated_minutes"] else "",
                                     f"{s['weight']} (est.)" if s["weight"] else ""] if x)
        have = [c for c in s["checks"] if c["status"] == "have"]
        missing = [c for c in s["checks"] if c["status"] in ("missing", "short")]
        check = [c for c in s["checks"] if c["status"] == "check amount"]
        body = [meta, f"[dim]Why:[/dim] {s['explanation']}" if s["explanation"] else ""]
        body.append("You have: " + ", ".join(
            (f"[yellow]{c['ingredient']}*[/yellow]" if c["expiring"] else c["ingredient"]) for c in have))
        if missing:
            body.append("Missing: " + ", ".join(
                c["ingredient"] + (" (short)" if c["status"] == "short" else "") +
                (f" -> use {c['substitute']}?" if c["substitute"] else "") for c in missing))
        if check:
            body.append("Check amount: " + ", ".join(c["ingredient"] for c in check))
        body.append(f"[dim]id {rec['id']}" + (f" | cook: fridgemate cook {rec['id']}" if can_cook else "") +
                    f" | shopping: fridgemate shopping from-recipe {rec['id']}[/dim]")
        console.print(Panel("\n".join(b for b in body if b), title=head, title_align="left"))
    if r["suggestions"]:
        console.print("[dim]* = expiring soon or offered by a roommate[/dim]")


def options(cuisine, time, weight, servings) -> dict:
    return {"cuisine": cuisine, "max_minutes": time, "weight": weight, "servings": servings}


@recipes_app.command("suggest")
def recipes_suggest(cuisine: Optional[str] = typer.Option(None, help="e.g. Italian; leave out to let the AI decide"),
                    time: Optional[int] = typer.Option(None, help="max cooking minutes"),
                    weight: Optional[str] = typer.Option(None, help="light, medium or heavy"),
                    servings: int = typer.Option(2, min=1, max=10),
                    trace: bool = typer.Option(False, "--trace", help="show the agent's steps")):
    """F07: the agent suggests recipes from your fridge, using expiring food first."""
    with console.status("The recipe agent is working..."):
        r = call(client.post, "/api/recipes/suggest", options(cuisine, time, weight, servings))
    show_recipes(r, can_cook=True)
    if trace:
        show_trace(r["trace"])


@recipes_app.command("find")
def recipes_find(ingredients: str = typer.Argument(..., help='comma separated, e.g. "chicken, rice, onion"'),
                 cuisine: Optional[str] = None, time: Optional[int] = None, weight: Optional[str] = None,
                 servings: int = typer.Option(2, min=1, max=10)):
    """F10: quick finder for ingredients you type (not from the fridge)."""
    body = options(cuisine, time, weight, servings) | {"ingredients": [x for x in ingredients.split(",") if x.strip()]}
    with console.status("Searching..."):
        r = call(client.post, "/api/recipes/find", body)
    show_recipes(r, can_cook=False)


@recipes_app.command("show")
def recipes_show(recipe_id: str):
    """Show a recipe's ingredients and instructions."""
    r = call(client.get, f"/api/recipes/{recipe_id}")
    console.print(f"[bold]{r['name']}[/bold] {r['cuisine']}")
    for i in r["ingredients"]:
        console.print(f"  - {i['measure']} {i['name']}")
    console.print(r["instructions"])


@recipes_app.command("cuisines")
def recipes_cuisines():
    console.print(", ".join(call(client.get, "/api/recipes/cuisines")))


@app.command()
def cook(recipe_id: str, servings: int = typer.Option(2, min=1, max=10),
         leftovers: int = typer.Option(0, help="portions left over (0 = none)"),
         location: str = typer.Option("fridge", help="where to keep leftovers")):
    """F09: cook a recipe and take the ingredients out of the inventory."""
    p = call(client.get, f"/api/recipes/{recipe_id}/cook", params={"servings": servings})
    if not p["usages"]:
        fail("none of this recipe's ingredients are in your inventory")
    t = Table(title=f"Cooking {p['recipe']['name']}")
    t.add_column("Take")
    t.add_column("From item")
    for u in p["usages"]:
        t.add_row(f"{u['amount']:g} {u['unit']}", u["item_name"])
    console.print(t)
    short = [c["ingredient"] for c in p["checks"] if c["status"] in ("missing", "short")]
    if short:
        console.print(f"[yellow]Not in stock: {', '.join(short)}[/yellow]")
    if not typer.confirm("Take these amounts from the inventory?", default=True):
        console.print("Cancelled.")
        return
    body = {"usages": [{"item_id": u["item_id"], "amount": u["amount"], "unit": u["unit"]} for u in p["usages"]],
            "leftover_portions": leftovers or None, "leftover_location": location}
    console.print(f"[green]{call(client.post, f'/api/recipes/{recipe_id}/cook', body)['message']}[/green]. "
                  "Undo with: fridgemate undo")


# ---------------- F11 shopping ----------------

@shopping_app.command("list")
def shopping_list():
    """Your shopping list plus Shared items, by store section."""
    r = call(client.get, "/api/shopping")
    if not r["count"]:
        console.print("Your shopping list is empty.")
    for section, lines in r["sections"].items():
        console.print(f"[bold]{section}[/bold]")
        for i in lines:
            mark = "[x]" if i["checked"] else "[ ]"
            console.print(f"  {mark} {i['name']} {qty(i['quantity'])}  [dim]{', '.join(i['reasons'])}"
                          f"{' (Shared)' if i['shared'] else ''}  {i['id'][:8]}[/dim]")


@shopping_app.command("add")
def shopping_add(name: str, amount: Optional[float] = typer.Argument(None), unit: Optional[str] = typer.Argument(None),
                 shared: bool = typer.Option(False, "--shared")):
    """Add an item by hand (duplicates are merged)."""
    i = call(client.post, "/api/shopping", {"name": name, "amount": amount, "unit": unit, "shared": shared})
    console.print(f"On the list: {i['name']} {qty(i['quantity'])}")


def _shopping_ref(ref: str) -> dict:
    lines = [i for s in call(client.get, "/api/shopping")["sections"].values() for i in s]
    match = [i for i in lines if i["id"].startswith(ref.lower())] or [i for i in lines if i["name"].lower() == ref.lower()]
    if len(match) != 1:
        fail(f"no single shopping item matches '{ref}'")
    return match[0]


@shopping_app.command("check")
def shopping_check(item: str, undo_check: bool = typer.Option(False, "--uncheck")):
    """Tick an item (by id prefix or name)."""
    line = _shopping_ref(item)
    call(client.patch, f"/api/shopping/{line['id']}", {"checked": not undo_check})
    console.print(f"{'Unchecked' if undo_check else 'Checked'} {line['name']}.")


@shopping_app.command("clear")
def shopping_clear():
    """Remove all checked items."""
    console.print(f"Removed {call(client.delete, '/api/shopping/checked')['removed']} checked item(s).")


@shopping_app.command("from-recipe")
def shopping_from_recipe(recipe_id: str, servings: int = 2):
    """Add a recipe's missing ingredients to your list."""
    added = call(client.post, f"/api/recipes/{recipe_id}/missing-to-shopping", params={"servings": servings})["added"]
    console.print(f"Added {len(added)} item(s): " + ", ".join(i["name"] for i in added) if added else
                  "You already have everything.")


# ---------------- F12 natural-language commands ----------------

def show_trace(trace: Optional[dict]) -> None:
    if not trace:
        return
    console.print(f"[dim]Agent trace ({trace['agent']}):[/dim]")
    for s in trace["steps"]:
        console.print(f"[dim]  {s['kind']:6} {s['tool'] or '':26} {s['detail'][:110]}[/dim]")


@app.command("do")
def do(message: str = typer.Argument(..., help='e.g. "I finished the milk and bought 6 eggs"'),
       yes: bool = typer.Option(False, "--yes", "-y", help="confirm without asking"),
       trace: bool = typer.Option(False, "--trace")):
    """F12: tell the fridge agent what happened in plain English."""
    with console.status("Thinking..."):
        r = call(client.post, "/api/command", {"message": message})
    console.print(f"[cyan]Fridgemate:[/cyan] {r['reply']}")
    if trace:
        show_trace(r["trace"])
    if r["question"]:
        console.print(f"[cyan]?[/cyan] {r['question']}  [dim](answer with: fridgemate do \"...\")[/dim]")
    p = r["proposal"]
    if not p:
        return
    console.print("[bold]Proposed changes:[/bold]")
    for c in p["changes"]:
        console.print(f"  - {c}")
    if r["question"] and not yes:
        console.print("[dim]Answer the question first, or confirm these now.[/dim]")
    if yes or typer.confirm("Confirm these changes?", default=True):
        for line in call(client.post, f"/api/command/{p['id']}/confirm")["done"]:
            console.print(f"  [green]done[/green] {line}")
        console.print("Undo the last one with: fridgemate undo")
    else:
        call(client.post, f"/api/command/{p['id']}/cancel")
        console.print("Cancelled, nothing changed.")


# ---------------- F13 meal plan ----------------

def show_plan(p: Optional[dict]) -> None:
    if not p:
        console.print("No meal plan yet. Make one with: fridgemate plan new --days 3")
        return
    if p["needs_update"]:
        console.print(Panel("Your stock changed, so some meals no longer fit. Run: fridgemate plan replan", style="yellow"))
    for m in p["meals"]:
        s = m["suggestion"]
        day = date.fromisoformat(m["day"]).strftime("%a %b %d")
        flag = " [red](outdated)[/red]" if m.get("outdated") else ""
        if s:
            ai = " [magenta](AI-generated)[/magenta]" if s["recipe"]["ai_generated"] else ""
            uses = ", ".join(c["item_name"] for c in s["checks"]
                             if c["status"] in ("have", "check amount") and c["item_name"] not in (None, "kitchen staple"))
            missing = ", ".join(c["ingredient"] for c in s["checks"] if c["status"] in ("missing", "short"))
            console.print(f"[bold]{day}[/bold] meal {m['slot']}: {s['recipe']['name']}{ai}{flag}  [dim]id {s['recipe']['id']}[/dim]")
            console.print(f"    uses: {uses}" + (f" | missing: {missing}" if missing else ""))
            if s["explanation"]:
                console.print(f"    [dim]{s['explanation']}[/dim]")
    for d in p["missing_days"]:
        console.print(f"[yellow]{d}: no meal planned[/yellow]")
    for n in p["notes"]:
        console.print(f"[yellow]{n}[/yellow]")


@plan_app.callback()
def plan_default(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        show_plan(call(client.get, "/api/meal-plan"))


@plan_app.command("new")
def plan_new(days: int = typer.Option(3, min=3, max=5), meals: int = typer.Option(1, min=1, max=2),
             time: Optional[int] = typer.Option(None, help="max cooking minutes"),
             trace: bool = typer.Option(False, "--trace")):
    """Plan the next 3 to 5 days around food that expires soon."""
    with console.status("The meal-plan agent is planning..."):
        p = call(client.post, "/api/meal-plan", {"days": days, "meals_per_day": meals, "max_minutes": time})
    show_plan(p)
    if trace:
        show_trace(p.get("trace"))


@plan_app.command("replan")
def plan_replan(time: Optional[int] = None):
    """Re-plan only the meals that no longer fit."""
    with console.status("Re-planning..."):
        show_plan(call(client.post, "/api/meal-plan/replan", params={"max_minutes": time} if time else None))


# ---------------- F14 costs ----------------

@costs_app.callback()
def costs_default(ctx: typer.Context, month: Optional[str] = typer.Option(None, help="YYYY-MM, default this month")):
    """Who paid what for Shared items, and who owes whom."""
    if ctx.invoked_subcommand is not None:
        return
    r = call(client.get, "/api/costs", params={"month": month} if month else None)
    console.print(f"[bold]Shared costs for {r['month']}[/bold]")
    if r["only_member"]:
        console.print("You're the only member, so there's nothing to split.")
    t = Table()
    for col in ("Item", "Price", "Paid by", "Date"):
        t.add_column(col)
    for p in r["purchases"]:
        t.add_row(p["item"], f"${p['price']}", p["payer"], p["date"])
    console.print(t)
    for m in r["members"]:
        console.print(f"  {m['name']}: paid ${m['paid']}, share ${m['share']}, balance ${m['balance']}")
    for s in r["settlements"]:
        console.print(f"  [bold]{s['from']} pays {s['to']} ${s['amount']}[/bold]  "
                      f"[dim](mark paid: fridgemate costs paid {s['from_id'][:8]} {s['to_id'][:8]} {s['amount']})[/dim]")
    if not r["settlements"] and not r["only_member"]:
        console.print("  Everyone is settled up.")
    for i in r["missing_price"]:
        console.print(f"  [yellow]Missing price:[/yellow] {i['name']} (fridgemate items edit {i['id'][:8]} ...)")


@costs_app.command("paid")
def costs_paid(from_member: str, to_member: str, amount: float):
    """Record a payment (member id prefixes from the costs view)."""
    members = call(client.get, "/api/household")["members"]

    def pick(ref):
        m = [x for x in members if x["id"].startswith(ref) or x["name"].lower() == ref.lower()]
        if len(m) != 1:
            fail(f"no single member matches '{ref}'")
        return m[0]["id"]

    call(client.post, "/api/costs/payments", {"from_id": pick(from_member), "to_id": pick(to_member), "amount": amount})
    console.print("[green]Payment recorded.[/green]")


def main() -> None:
    app(prog_name="fridgemate")


if __name__ == "__main__":
    main()
