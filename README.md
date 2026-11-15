# Fridgemate

An AI agent web app for roommates who share one fridge. It tracks who owns what, estimates expiry dates, imports receipts, suggests recipes that use food before it spoils, plans waste-rescue meals, builds shopping lists, splits shared costs, and lets roommates offer and claim food that is about to expire.

EECS 3311 Software Design course project, York University, Fall 2026.
Author: Mohammad Mashrur Mahtab Mahi.

- **Web GUI:** React + TypeScript (Vite)
- **CLI:** Python `typer`
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

## 6. Tests

```bash
python -m pytest -q
```

The tests never call the real Gemini or TheMealDB APIs. They use a scripted fake LLM and fake recipe source.

## 7. Features

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

## 8. Project layout

```
server/
  api/             FastAPI app, TokenVerifier and the 10 routers
  application/     FridgemateFacade (Facade), RequestContext, composition root
  domain/          model (State pattern), services (Observer, Strategy), commands (Command)
  agent/           BaseAgent tool loop, RecipeAgent, MealPlanAgent, FridgeCommandAgent, ReceiptParser, tools
  infrastructure/  LLM adapters + LLMClientFactory, TheMealDB adapter, SQLite repositories
cli/               typer CLI, FridgemateClient, TokenStore
web/               React + TypeScript GUI
tests/             pytest suite
docs/              Stage 1 report and diagrams, design changes
```

## License

MIT
