# Fridgemate

An AI agent web app for roommates who share one fridge. It tracks who owns what, estimates expiry dates, imports receipts, suggests recipes that use food before it spoils, plans waste-rescue meals, builds shopping lists, splits shared costs, and lets roommates offer and claim food that is about to expire.

EECS 3311 Software Design course project, York University, Fall 2026.
Author: Mohammad Mashrur Mahtab Mahi.

- **Web GUI:** React + TypeScript (Vite)
- **CLI:** Python `typer` (`fridgemate`, talks to the server) and a standalone agent CLI (`fridgemate-agent`, no server needed)
- **Server:** Python 3.12 + FastAPI, SQLite database
- **AI:** Google Gemini Flash (Ollama as a local backup), called only from the server
- **Recipes:** TheMealDB (free test key)

Design documents: [Stage 1 report](docs/stage1/report.md), [design changes in Stage 2](docs/design-changes.md).

---

## 1. Prerequisites

| Tool | Version | Check with |
|---|---|---|
| Python | 3.12 or newer | `python --version` (Windows) or `python3 --version` (Mac) |
| Node.js | 18 or newer (only for the web GUI) | `node -v` |
| Git | any | `git --version` |

You also need a free **Gemini API key** for the AI features: https://aistudio.google.com/apikey.
Without a key the app still runs. Storage location and expiry estimates fall back to rule tables, and the agent features show "AI unavailable".

## 2. Install

Run these from the project folder (the one with this README). On **Windows use Git Bash**.

```bash
# 1. create and turn on a virtual environment
python -m venv .venv            # Mac: python3 -m venv .venv
source .venv/Scripts/activate   # Mac: source .venv/bin/activate

# 2. install the server and the CLI (this also creates the `fridgemate` command)
pip install -r requirements.txt
pip install -e .

# 3. install and build the web GUI
cd web
npm install
npm run build
cd ..
```

## 3. Configure your key (local only)

```bash
cp .env.example .env
```

Open `.env` and replace `YOUR_LOCAL_API_KEY_HERE` with your Gemini key. The `.env` file is git-ignored, so it is never committed. Never put a key anywhere else.

| Setting | Meaning |
|---|---|
| `LLM_PROVIDER` | `gemini` (default), `ollama` (local model) or `none` (AI off) |
| `GEMINI_API_KEY` | your key |
| `GEMINI_MODEL` | default `gemini-3.5-flash` (`GEMINI_THINKING=low` keeps answers fast) |
| `DATABASE_PATH` | SQLite file, created automatically (default `fridgemate.db`) |

## 4. Run

**Start the server** (leave this terminal open):

```bash
python -m server
```

**GUI:** open http://127.0.0.1:8000 in a browser. The server also serves the built web app. Register, then create a household or join one with an invite code.

For web development with hot reload, run `cd web && npm run dev` in a second terminal and open http://localhost:5173.

**CLI:** open a second terminal, activate the virtual environment again, then:

```bash
fridgemate --help            # or: python -m cli --help
```

## 5. Example usage (CLI)

```bash
fridgemate register                        # asks for email, name, password
fridgemate household create "Apt 4B"       # prints an invite code
fridgemate household join ABCD123456       # a roommate joins with the code

fridgemate items add Milk 1 l              # AI suggests location and expiry (F01, F02, F04)
fridgemate items add Spinach 200 g --location fridge --expiry 2026-11-17
fridgemate items add Rice 2 kg --shared --price 12 --paid-by-me
fridgemate items list
fridgemate undo

fridgemate alerts                          # expiring soon, then expired (F05)
fridgemate receipt import receipt.jpg      # AI reads a receipt, you review it (F03)
fridgemate recipes suggest --time 30 --trace        # recipe agent (F07, F08)
fridgemate recipes find "chicken, rice, onion"      # quick finder (F10)
fridgemate cook 52772 --leftovers 2        # cook and deduct stock (F09)
fridgemate shopping list                   # F11
fridgemate do "I finished the milk and bought 6 eggs"  # natural-language command (F12)
fridgemate plan new --days 3               # waste-rescue meal plan (F13)
fridgemate costs                           # who owes whom (F14)
fridgemate offer spinach --note "half a bag"   # F15
fridgemate claim spinach                   # (as a roommate)
fridgemate notifications
```

To try two users on one computer with the CLI, give each user their own token folder:
`FRIDGEMATE_HOME=~/.fridgemate-bob fridgemate login`.

## 6. Standalone agent CLI (no server)

`fridgemate-agent` runs the agent directly from a terminal. It needs no server and no login: it reads tasks from a file, from standard input or from the command line, runs each one, and prints the result. It uses the same Facade, agents and database code as the server, so the results match the GUI.

```bash
fridgemate-agent --llm gemini --input examples/task.txt     # tasks from a file
echo "I bought 6 eggs" | fridgemate-agent                   # tasks from standard input
fridgemate-agent --input - < examples/task.txt              # same, with "-" for standard input
fridgemate-agent "add Milk 1 l" "recipes 30"                # tasks as arguments
python -m cli.agent_cli --help                              # same program without the installed command
```

**Options**

| Option | Meaning |
|---|---|
| `-i FILE`, `--input FILE` | File with one task per line. `-` reads standard input. Without `--input`, the tasks come from the arguments, or from standard input when it is piped. |
| `-o FILE`, `--output FILE` | Also write the results to this file. |
| `--llm gemini\|ollama\|none` | LLM to use. Default: `LLM_PROVIDER` in `.env`. `none` turns AI off (rule fallbacks only). |
| `--model NAME` | Model for the chosen LLM, e.g. `gemini-3.5-flash`. Default: from `.env`. |
| `--db PATH` | SQLite database file. Default: `DATABASE_PATH` in `.env`. |
| `--memory` | Use a fresh in-memory database; nothing is saved. |
| `--dry-run` | Show what the agent would change without changing anything. |
| `--trace` | Print every agent step (tool calls and final answer). |
| `-h`, `--help` | Show all options and task keywords. |

The exit code is 0 when every task worked and 1 when any task failed. A bad task prints `Error: ...` and the next task still runs.

**Task lines** (blank lines and lines starting with `#` are skipped)

| Task | Feature |
|---|---|
| `add <name> <amount> <unit>` | Add an item; AI picks the location and expiry (F01, F02, F04) |
| `list` | Show the inventory (F01) |
| `alerts` | Items that expire soon or have expired (F05) |
| `receipt <file>` | Read a receipt photo or `.txt` file and add its items (F03) |
| `recipes [minutes]` | Recipe agent on what is in the fridge (F07, F08) |
| `find <a, b, c>` | Recipes for the listed ingredients (F10) |
| `plan [days]` | Waste-rescue meal plan for 1 to 7 days (F13) |
| `shopping` | Show the shopping list (F11) |
| anything else | Natural-language fridge agent, e.g. `I used 2 eggs` (F12) |

The standalone CLI uses one local profile ("Local user", household "My fridge"), created on the first run.

**Working example.** [`examples/task.txt`](examples/task.txt):

```text
add Milk 1 l
add Spinach 200 g
add Chicken breast 500 g
I bought 6 eggs and used half of the spinach
list
alerts
recipes 30
```

```bash
fridgemate-agent --llm gemini --memory --input examples/task.txt
```

Output from a real run (shortened):

```text
=== Task 1: add Milk 1 l
Added Milk (1 l) to the fridge, expires 2026-12-01.
  - Fridge: Perishable dairy product requires cold storage to stay safe (AI)
  - Estimated 2026-12-01 (AI)
...
=== Task 4: I bought 6 eggs and used half of the spinach
Agent: I've proposed adding 6 eggs to your fridge and using 100g of your spinach.
  - Add 6 pcs eggs to the fridge
  - Use 100 g of Spinach
  Done: Add 6 pcs eggs to the fridge
  Done: Use 100 g of Spinach

=== Task 5: list
  fridge   Chicken breast       500 g      expires 2026-11-26 (Expiring soon)
  fridge   Milk                 1 l        expires 2026-12-01 (Fresh)
  fridge   Spinach              100 g      expires 2026-12-01 (Fresh)
  fridge   eggs                 6 pcs      expires 2026-12-22 (Fresh)

=== Task 6: alerts
  Expiring soon  Chicken breast (500 g), expires 2026-11-26

=== Task 7: recipes 30
1. Quick Chicken & Spinach Scramble (AI-written, about 15 min)
   Why: Uses your expiring chicken breast and fresh spinach for a quick, high-protein meal.
   Uses: Chicken breast, Spinach, eggs, Milk
...
Done: 7 task(s), 0 failed. AI (gemini): 16 call(s), 11707 input and 1572 output tokens.
```

This example uses about 16 AI calls. The free Gemini key allows about 20 calls per model per day; when a model runs out, the next model in `GEMINI_FALLBACK_MODELS` is used.

## 7. Tests

```bash
python -m pytest -q
```

The tests never call the real Gemini or TheMealDB APIs. They use a scripted fake LLM and fake recipe source.

## 8. Features

| ID | Feature | GUI page | CLI | AI |
|---|---|---|---|---|
| F01 | Manage inventory items (with undo) | Inventory | `items ...`, `undo` | no |
| F02 | Suggest storage location | Inventory > Add item | `items add`, `items suggest` | AI + rule fallback |
| F03 | Import receipt | Receipt | `receipt import` | AI |
| F04 | Estimate expiry | Inventory > Add item | `items add`, `items suggest` | AI + rule fallback |
| F05 | Expiry alerts ("Use it first") | Inventory | `alerts` | no |
| F06 | Household and preferences | Household | `household ...`, `prefs set` | no |
| F07 | Recipe suggestions (agent) | Recipes | `recipes suggest` | AI agent |
| F08 | Missing ingredients and substitutes | Recipe cards | `recipes suggest` | hybrid |
| F09 | Cook recipe (leftovers, undo) | Cook this | `cook` | no |
| F10 | Quick Finder | Quick Finder | `recipes find` | AI agent |
| F11 | Shopping list | Shopping | `shopping ...` | no |
| F12 | Natural-language fridge commands | Chat | `do` | AI agent |
| F13 | Waste-rescue meal plan | Meal Plan | `plan new`, `plan replan` | AI agent |
| F14 | Split shared costs | Costs | `costs` | no |
| F15 | Offer and claim expiring items | Inventory, Notifications | `offer`, `claim`, `notifications` | no |

## 9. Project layout

```
server/
  api/             FastAPI app, TokenVerifier and the 10 routers
  application/     FridgemateFacade (Facade), RequestContext, composition root
  domain/          model (State pattern), services (Observer, Strategy), commands (Command)
  agent/           BaseAgent tool loop, RecipeAgent, MealPlanAgent, FridgeCommandAgent, ReceiptParser, tools
  infrastructure/  LLM adapters + LLMClientFactory, TheMealDB adapter, SQLite repositories
cli/               typer CLI, FridgemateClient, TokenStore; agent_cli.py = standalone agent CLI
examples/          task.txt for the standalone agent CLI
web/               React + TypeScript GUI
tests/             pytest suite
docs/              Stage 1 report and diagrams, design changes
```

## License

MIT
