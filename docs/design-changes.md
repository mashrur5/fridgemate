# Design changes from Stage 1

Each entry: Original design -> Implemented change -> Reason -> Impact. Report section 4 is built from this file.

| # | Original design | Implemented change | Reason | Impact |
|---|---|---|---|---|
| 1 | `FoodItem` had no household link | Added `household_id` | Repositories look items up by household | `FoodItem`, `ItemRepository.find_by_household` |
| 2 | Visibility rule only described in text | Added `FoodItem.visible_to(member)` and `freshness_label()` | One place for the own-or-Shared rule (G2) | `FoodItem`, all services |
| 3 | `InventoryService` had no single-item lookup or offer withdrawal | Added `get_item()` and `withdraw_offer()` | Undoing an offer needs a withdraw operation | `InventoryService`, `OfferItemCommand` |
| 4 | Only Postgres repositories | Added `InMemory*Repository` classes | Fast tests and running without a database | Persistence layer |
| 5 | `InventoryService` used the system date | Takes a `today` callable | Tests can control the date | `InventoryService` |
| 6 | `Quantity` supported g, kg, ml, l, pcs | Added tsp, tbsp, cup, oz, lb | TheMealDB measures use kitchen units | `Quantity`, `UnitConverter` |
| 7 | `Member.auth0_id` | Renamed to `Member.account_id` | Auth0 replaced by built-in accounts (see 8) | `Member`, `AccountService` |
| 8 | Auth0 Universal Login and Device flow (UC16) | Built-in accounts: PBKDF2-hashed passwords and random session tokens; CLI `fridgemate login` asks for email and password | Auth0 tenant setup was the riskiest part with the time left; accounts do not count as a feature | `AccountService`, `TokenVerifier`, `TokenStore`; `Auth0Client` and `DeviceLogin` removed |
| 9 | Neon serverless PostgreSQL via psycopg | Local SQLite file via Python's built-in `sqlite3`; same repository interfaces | No database account needed to run or grade the app; claims still use one conditional `UPDATE` | `Database`, `Sqlite*Repository` replace `Postgres*Repository` |
| 10 | Kitchen staples not mentioned | Water, salt and pepper always count as "have" in `StockValidator` | Nobody tracks salt in a fridge app; otherwise every recipe shows them missing | F08 |
| 11 | Member linked to a household only through the household's member list | `Member.household_id` | Simple lookup of a member's household when loading the request context | `Member`, `MemberRepository.find_by_household` |
| 12 | Using an item up raised the same "removed" event as deleting it | `InventoryService.deduct` sends "used_up" when an item reaches zero | The shopping list must add used-up items but not items the user deleted by mistake | Observer events |
| 13 | Cost split read Shared items straight from the inventory | `CostSplitService` is also an Observer and records a `Purchase` when a priced Shared item is added | Items get used up and deleted, but what was paid must still be split | F14, Observer pattern gains a 4th observer |
| 14 | F11 used the LLM to match similar names and pick store sections | Deterministic synonym list and keyword section table | Faster and free; the Stage 1 "AI unavailable" behaviour is now the normal path | F11 is deterministic instead of hybrid |
| 15 | "Gemini Flash" as one model | `gemini-3.5-flash` with thinking level "low", plus a fallback list (`gemini-3-flash-preview`, `gemini-3.1-flash-lite`) used when a model's daily free quota is used up | `gemini-2.5-flash` was retired for new keys, and free keys allow only about 20 requests per model per day | `GeminiClient` (Adapter) now handles quota errors itself; agents are unchanged |
| 16 | Recipe agent wrote its own recipe when "too few fit" | Prompt tells it to keep every validated TheMealDB recipe that uses an expiring item and only write its own to reach 3 | In live tests the model preferred writing all recipes itself | F07, F10 |
| 17 | CLI only talked to the server (needs `python -m server` and a login) | New standalone agent CLI `fridgemate-agent` (`cli/agent_cli.py`, `AgentRunner`): runs tasks from a file (`--input task.txt`), standard input or arguments, with `--llm`, `--model`, `--db`, `--memory`, `--dry-run`, `--trace`, `--output`; builds the Facade in-process through `build_facade` and uses a local profile | Instructor feedback (Nov 20): the agent must run directly from a terminal on a task file, as required for Stage 3 | New interface over the same Facade, agents and repositories; no domain changes. Covers F01-F05, F07, F08, F10-F13 |
