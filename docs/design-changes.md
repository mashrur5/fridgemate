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
