# Fridgemate: Stage 1 Design Report

EECS 3311 Software Design
Author: Mohammad Mashrur Mahtab Mahi
Repository: https://github.com/mashrur5/fridgemate

## 1. Defining my agent project

## 1.1 Project Description

### 1.1.1 Problem and Motivation

I live with roommates, and we all share one fridge. It sounds simple, but it causes the same problems every week. Nobody knows what they can cook with what is already there, so we end up ordering food or buying more groceries. Items get pushed to the back, and after a few days it is hard to remember whose milk or vegetables are whose. By the time someone notices, the food has usually gone bad.

These problems come down to three things:

- Deciding what to cook: It is hard to know which meals you can make with what you have, especially when you also have to think about how much time you have and what you feel like eating.
- Losing track of ownership: In a shared fridge, food gets forgotten because no one is sure who it belongs to.
- Food waste: Without tracking expiry dates, food spoils before anyone uses it, which wastes both food and money.

Fridgemate is an AI agent that helps a shared household manage its food. It tracks what is in the fridge, freezer, and pantry, along with who owns each item. It also estimates when items will expire, reads grocery receipts, and suggests recipes and meal plans that use food before it goes bad. If one of my items is about to expire and I know I won't use it, I can offer it to my roommates instead of throwing it out (#NoWaste)!

### 1.1.2 Target Users

Fridgemate is built for students and young adults who live in shared housing, such as roommates/housemates in an apartment or house or even residence. Most of these users are busy and on a tight budget (broke college students), so throwing away food actually hurts. They also share a fridge with people they may not talk to every day, which is why ownership and sharing are a big part of the design.

### 1.1.3 What the Agent Can Do

Fridgemate has 15 features in three groups.
| Group | Features |
| --- | --- |
| Tracking food | F01 Inventory management, F02 AI storage placement, F03 Receipt import, F04 Expiry estimation and tracking, F05 Expiring-soon alerts, F06 Household members, ownership, and preferences |
| Cooking | F07 Constraint-based recipe agent, F08 Missing-ingredient detection and substitution, F09 Cook recipe, F10 Quick Recipe Finder |
| Planning and sharing | F11 Shopping list generation, F12 Natural-language fridge commands, F13 Waste-rescue meal plan, F14 Shared grocery cost split, F15 Share before it spoils |

A few examples show what this looks like in practice:

- **Recipe suggestions:-** The user picks a cuisine, a cooking time (under 15, 15 to 30, 30 to 60, or over 60 minutes), a meal weight (light, medium, or heavy), and the number of servings. Each option also has "Let AI decide." The agent then suggests recipes that use the user's own food and anything shared, starting with what expires first.
- **Receipt import:-** The user uploads a photo of a grocery receipt, and the agent turns it into a clean list of items to confirm before saving.
- **Plain-English commands:-** The user can type something like "I finished the milk, add 6 eggs," and the agent turns it into the right inventory changes.
- **Sharing before it spoils:-** When an item is about to expire, its owner can offer it to the household. Everyone else gets a notification, and the first person to claim it becomes the new owner.

Besides these 15 features, Fridgemate also has register, login, and change password, which are handled through Auth0. I don't count these as features, since the instructions say login and change password don't count, but every other feature depends on them to know who owns what. Creating a household and inviting roommates is part of F06.

### 1.1.4 Why an AI Agent Fits This Problem

Picking a meal sounds easy, but it involves a lot of things at once: what is in stock, who owns it, what is about to expire, how much time the user has, what kind of food they want, and how many people they are cooking for. A single call to an LLM cannot handle this reliably, because the model has no idea what is in my fridge and it may make up ingredients that are not there. That is why Fridgemate uses an agent that works in steps and checks its work with tools.

The agent shows the following behaviors:

- **Tool use:-** It reads the inventory, checks expiry dates, searches for recipes, and converts units by calling tools instead of guessing.
- **Multi-step planning:-** The recipe agent filters the inventory, ranks items by expiry, searches for recipes, checks them against real stock, and suggests substitutes, all in one loop. The meal plan agent plans 3 to 5 days ahead and re-plans when something changes.
- **Reasoning and decision making:-** The agent ranks recipes by balancing expiry dates, time limits, and preferences. When the user selects "Let AI decide" for an option, the agent makes that choice itself and explains why.
- **Retrieval:-** Recipes come from TheMealDB, an external recipe database, so suggestions are based on real recipes. If it doesn't have enough recipes that fit, the agent writes one itself, labels it as AI-generated, and checks it against the real stock like any other recipe.
- **Memory:-** The agent keeps the recent conversation, so a follow-up like "use that one instead" makes sense. It also remembers each member's dietary restrictions and dislikes.
- **Understanding messy input:-** It reads receipt photos where items show up as short codes like "GRN ONIO," and it understands commands written in plain English.

Not every feature needs AI, though. Splitting costs or subtracting ingredients after cooking has one correct answer, so regular code handles those. I only use the AI where judgment is actually needed.

#### 1.1.5 AI Model

Fridgemate uses *Google Gemini Flash* through the Gemini API. I chose it for three reasons: it has a free tier, it supports tool calling, and it can read images, which receipt import needs. Gemini is only ever called from the server, so the API key never reaches a user's browser. Since the free tier has rate limits, the server retries failed calls after a short wait.

All LLM calls go through one *LLMClient* interface. If Gemini ever becomes a problem, a local model run through Ollama can replace it by changing the configuration only, without touching the rest of the system.

#### 1.1.6 How the AI Interacts with the Rest of the System

Neither the LLM nor the clients ever read or change data directly. Every request goes through the same path:

1. The user does something in the web app or types a CLI command. The client sends a request to the Fridgemate server, along with the user's login token.
2. The server checks the token and finds the user's household. From then on, every step only sees that household's data.
3. The request reaches *FridgemateFacade*, the single entry point to the system. It sends regular requests, like adding an item or splitting costs, to domain services, and AI requests, like recipe suggestions or meal plans, to an agent.
4. The agent builds a prompt and calls *LLMClient*, giving the model a set of tools it can use.
5. When the model asks for a tool, the agent runs it. Tools only talk to domain services, and those services apply the ownership, household, and expiry rules.
6. The model's answer is checked against an expected format, and every recipe is checked against the real stock before it is sent back.
7. If the AI suggests a change to the inventory, the user confirms it first, and then it is carried out as a command that can be undone.

Because of this setup, rules like "never use a roommate's food" and "never suggest expired food" are enforced by regular code on the server. The system does not rely on the LLM to follow them.

#### 1.1.7 Overall Architecture

Fridgemate is a live web product with two sides. The client side is what users see: a web app that runs in any browser, including on phones, and a command-line tool. The server side does all the real work. It holds the business rules, runs the AI agents, and is the only part that talks to the database and outside services. Since the clients only send requests and show results, they stay simple, and both behave the same way.

| Side | Layer | Contains | Responsibility |
| --- | --- | --- | --- |
| Client | Presentation | React web pages, CLI commands | Take user input and show results |
| Client | Client gateway | API clients for the web app and the CLI, Auth0 login | Send requests to the server with the user's login token |
| Server | API | FastAPI routers, token verification | Check who the user is and pass the request on |
| Server | Application | `FridgemateFacade` | One entry point for every request |
| Server | Domain and Agent | Food items, services, commands, agents, tools | Business rules and AI reasoning |
| Server | Infrastructure | Neon database access, Gemini client, TheMealDB client | Storage and outside services |

Each roommate creates their own account and uses Fridgemate on their own device. Accounts are handled by Auth0. Users register with their email and password, Fridgemate asks for their name the first time they log in, and Auth0 sends an email if they need to reset their password, so passwords never reach Fridgemate at all. After logging in, a user either creates a household and gets an invite code, or joins their roommates' household with that code. The server only ever returns data from the user's own household, so different households never see each other's food.

All data is stored in one online PostgreSQL database hosted on Neon, so a change made on one device shows up on every other device. Notifications for shared items are saved there too, and the web app checks for new ones every minute. Since the server talks to the database only through repository interfaces such as *ItemRepository*, the database could be replaced later without changing the services, agents, or clients.

#### 1.1.8 Technology Stack

| Part | Choice |
| --- | --- |
| Web GUI | React with TypeScript |
| CLI | Python with typer |
| Server | Python 3.12 with FastAPI |
| Database | Neon (serverless PostgreSQL) |
| Accounts | Auth0 |
| LLM | Google Gemini Flash (Ollama as a backup) |
| Recipe data | TheMealDB |
| Hosting | Render for the server; the web app's host is chosen in nexr stage|
| Testing (Stage 3) | pytest and KUMA |

#### 1.1.9 Minimum Requirements

| Requirement | How Fridgemate meets it |
| --- | --- |
| GUI | A React web app that runs in any browser, including on phones, with pages for inventory, household, recipes, quick finder, meal plan, shopping list, cost split, notifications, and chat commands |
| CLI | A `fridgemate` command with subcommands for the same features, plus `login`, `logout`, and `change-password`. It calls the same server API as the web app |
| At least 10 features | 15 features: 6 deterministic, 4 hybrid, and 5 AI or agent |
| At least 5 design patterns | 7 patterns: Facade, Strategy, Command, Observer, State, Adapter, and Factory Method (Section 2.1) |
| AI model | Google Gemini Flash, called from the server |
| Agent behavior | Tool use, multi-step planning, reasoning, retrieval, and memory (Section 1.1.4) |

### 1.2 Feature Specification

This section describes each of Fridgemate's 15 features in detail. Every feature follows the same structure: what it does, how the user reaches it in the web app, its input and output, how much AI it uses, the steps it goes through, and what happens when something goes wrong. Most features can also be used from the CLI, so the matching command is listed under User Interaction. Register, login, and change password are described separately in 1.2.16, since they don't count as features.

#### 1.2.1 F01: Inventory Management

**Description:** This feature lets users keep track of everything in the household's fridge, freezer, and pantry. Users can add, edit, remove, search, and filter items. Each item stores its name, quantity, unit, location, owner, expiry date, price, and who paid for it. Every change can be undone.

**User Interaction:** The Inventory page shows all items grouped by location, with a search box and filters for location, owner, and freshness. The "Add item" button opens a form, and each item has Edit and Remove buttons. After any change, an Undo button appears. In the CLI, the same actions are available through `fridgemate items add`, `list`, `edit`, and `remove`.

**Input:**
- Item name and quantity (required)
- Unit, chosen from a fixed list such as g, kg, ml, L, or pieces
- Location (optional, since F02 can suggest one)
- Owner: the user, Shared, or a specific roommate (defaults to the user)
- Expiry date (optional, since F04 can estimate one)
- Price and who paid (optional, used by F14)
- For searching: a text query and any filters

**Output:** The updated inventory list, showing each item's location, owner, quantity, and freshness label, plus a short confirmation message.

**AI Involvement:** Deterministic. The only AI involved comes from F02 and F04, when the user leaves the location or expiry date empty.

**Expected Workflow:**
1. The user fills in the form and submits it.
2. The server checks the values, such as making sure the quantity is greater than zero.
3. If the location or expiry date is empty, the server gets a suggestion from F02 or F04.
4. The change is carried out as a command, saved to the database, and added to the user's undo history.
5. Other parts of the system that depend on the inventory, such as expiry alerts and the shopping list, are told about the change.
6. The page shows the updated list.

**Error/Alternative Cases:**
- **Missing or invalid values:** if the name is empty or the quantity is zero or negative, the form shows an error and nothing is saved.
- **Someone else's item:** a user tries to edit or remove a roommate's item. The app blocks it, since members can only change their own items or Shared ones.
- **Item already gone:** a roommate removed the item a moment earlier. The app says the item no longer exists and refreshes the list.
- **Server unreachable:** the app says it couldn't connect, nothing changes, and the user can try again.
- **Nothing to undo:** the user presses Undo after the server has restarted. The app explains there is nothing to undo.

#### 1.2.2 F02: AI Storage Placement

**Description:** When a user adds an item without choosing where it goes, the AI suggests the fridge, freezer, or pantry and gives a short reason. The user can accept the suggestion or pick a different place. If the AI is unavailable, a built-in rule table makes the suggestion instead.

**User Interaction:** In the Add Item form, the Location field starts on "Suggest for me." After the user types the item name, the suggestion appears with a one-line reason, for example "Freezer: ground beef keeps for months frozen." The user can keep it or choose another location. The same suggestions appear for each item in the receipt review popup in F03. In the CLI, leaving out `--location` prints the suggestion and asks the user to confirm it.

**Input:** The item name, plus any detail the user typed, such as "frozen peas" or "opened."

**Output:** A suggested location with a short reason, and whether it came from the AI or the rule table.

**AI Involvement:** Hybrid. The LLM makes the suggestion, but the answer must be one of the three locations, the rule table takes over when the AI fails, and the user always has the final say.

**Expected Workflow:**
1. The user enters an item name and leaves the location empty.
2. The server asks the LLM where the item should be stored, in a fixed answer format.
3. The answer is checked to make sure it is exactly one of Fridge, Freezer, or Pantry.
4. The suggestion and reason are shown to the user.
5. The user accepts or changes it, and the item is saved with that location.

**Error/Alternative Cases:**
- **AI unavailable or invalid answer:** the LLM is down, rate-limited, or returns something that isn't a valid location. The rule table makes the suggestion, and the app notes that it came from the rule table.
- **Item not in the rule table:** the app asks the user to choose, with Fridge preselected as the safest default.
- **Vague name:** for an unclear name like "stuff," the app asks the user to choose rather than guessing.
- **User override:** the user always wins, and their choice is saved without being questioned.

#### 1.2.3 F03: Receipt Import

**Description:** Instead of typing every item, the user uploads a photo of a grocery receipt. The AI reads it, turns short codes like "GRN ONIO" into clear names like "green onion," and pulls out each item's quantity and price. All the items then appear in a review popup, where the user decides who owns each one, removes anything that isn't accurate, and adds anything the AI missed. Nothing is saved until the user is happy with the list.

**User Interaction:** On the Receipt Import page, the user uploads a photo, or takes one with their phone's camera, and selects who paid. A popup then lists every item the AI found. Each item has a dropdown on its right to set the owner: Shared, the user, or a specific roommate. Each item also has a remove button, and the name, quantity, location, and expiry date can be edited. An "Add item" button at the bottom lets the user add anything the AI missed. Pressing Save adds everything to the inventory. In the CLI, `fridgemate receipt import photo.jpg` prints the items found and lets the user set owners, remove items, or add items before saving.

**Input:**
- A photo of the receipt (JPG or PNG)
- Who paid
- The owner of each item, chosen from the dropdown
- Any corrections, removals, or manually added items

**Output:** First, the review popup with all proposed items. After saving, the items are added to the inventory and the app shows a summary, such as "12 items added."

**AI Involvement:** AI. Gemini reads the image and cleans up the item names. Everything else is deterministic: the answer is checked against a fixed format, non-food lines are dropped, and nothing is saved until the user presses Save.

**Expected Workflow:**
1. The user uploads the photo and selects who paid.
2. The server sends the image to Gemini and asks for the items in a fixed format. The instructions make clear that text on the receipt is only data, never instructions.
3. The answer is checked, and lines that aren't food, such as bags, taxes, and deposits, are dropped.
4. Each item gets a location suggestion from F02 and an expiry estimate from F04.
5. The review popup shows all proposed items, with each owner set to the user by default.
6. The user sets owners, removes items that aren't accurate, and adds any missing ones.
7. When the user presses Save, the items are added to the inventory. To change something afterwards, the user edits or removes it on the Inventory page (F01).

**Error/Alternative Cases:**
- **Unreadable photo:** the photo is blurry or isn't a receipt. The app says it couldn't read it and suggests a clearer photo or adding items by hand.
- **Unclear lines:** some lines can't be read with confidence. Those items are marked "check this" in the popup so the user can fix or remove them.
- **Malformed AI answer:** the AI's answer doesn't match the expected format. The server retries once, then shows an error.
- **Hidden instructions:** the receipt contains text that tries to give the AI instructions. It is ignored and treated as an ordinary line.
- **Wrong file:** the file is too large or not an image. The app rejects it before uploading.
- **Rate limit:** Gemini's limit is reached, so the app asks the user to try again shortly.
- **Everything removed:** the user removes every item. Save is disabled, and the user can only close the popup.
- **Closed without saving:** the user closes the popup, and nothing is saved.

#### 1.2.4 F04: Expiry Estimation and Tracking

**Description:** Receipts don't show expiry dates, so the AI estimates one based on the item and where it's stored. For example, milk lasts about 7 days in the fridge but about 3 months frozen. The user can always edit the date. Each item also has a freshness state of Fresh, Expiring soon, or Expired, which controls what can be done with it: expired items can't be used in recipes or offered to roommates.

**User Interaction:** In the Add Item form and in the receipt review popup, the expiry field shows the estimate, marked "estimated," and the user can change it. On the Inventory page, every item has a colored freshness label. If the user moves an item, for example from the fridge to the freezer, the app offers a new estimate. In the CLI, `fridgemate items list` shows each item's expiry date and freshness.

**Input:**
- Item name and location
- The date the item was added
- An expiry date, if the user entered one

**Output:** An expiry date marked as either estimated or entered by the user, and a freshness label for each item.

**AI Involvement:** Hybrid. The LLM estimates shelf life, with the rule table as a fallback. Freshness is then worked out by regular code, using these rules:

| Freshness | Rule |
| --- | --- |
| Expired | The expiry date has passed |
| Expiring soon | The item expires within 3 days |
| Fresh | Anything else |

**Expected Workflow:**
1. An item is added without an expiry date.
2. The server asks the LLM how many days the item lasts in its location, in a fixed format.
3. The answer is checked to make sure it is a whole number within a sensible range.
4. The expiry date is set to the date added plus that number of days, and marked as estimated.
5. Whenever items are loaded, each item's freshness is worked out from its expiry date.
6. The labels are shown, and items that are expiring soon appear in F05's alerts.

**Error/Alternative Cases:**
- **AI unavailable or invalid answer:** the rule table gives the estimate instead.
- **Item not in the rule table:** the app uses a cautious default for that location and asks the user to check the date.
- **Date in the past:** the user enters an expiry date that has already passed. The item is saved as Expired, and the app shows a warning.
- **Item moved:** the app offers a new estimate for the new location, but the user can keep the old date.
- **User-entered dates:** a date the user typed is never replaced by an AI estimate.

#### 1.2.5 F05: Expiring-Soon Alerts and "Use It First" View

**Description:** This feature makes sure food that is about to go bad doesn't get forgotten. It shows the user which of their items and Shared items are expiring soon, sorted so the most urgent ones come first. Expired items are listed separately so the user can check and remove them. Each expiring item has an "Offer to household" button, which connects to F15.

**User Interaction:** When the user logs in, a banner at the top of the app shows how many items are expiring soon, for example "3 items expire in the next 3 days." Clicking it opens the "Use it first" tab on the Inventory page, which lists those items with the days left, location, and owner. Expiring items have an "Offer to household" button, and expired items have a Remove button. In the CLI, `fridgemate alerts` prints the same list.

**Input:** No typing is needed. The feature uses the user's own items and Shared items, their expiry dates, and today's date.

**Output:**
- A banner with the number of items expiring soon
- A list of expiring items, sorted with the soonest first
- A separate list of expired items

**AI Involvement:** Deterministic. Freshness comes from F04's rules, and sorting is by days left.

**Expected Workflow:**
1. The user opens the app, or the inventory changes.
2. The server loads the household's items and works out each item's freshness.
3. When the inventory changes, the alert list is updated automatically, so it never shows outdated information.
4. The list is narrowed to the user's own items and Shared items, then sorted by how soon each one expires.
5. The banner and the "Use it first" tab show the result.

**Error/Alternative Cases:**
- **Nothing expiring:** the tab says "Nothing is expiring soon," and no banner appears.
- **Expired items:** they can't be offered, so their Offer button is replaced by a Remove button.
- **Roommates' items:** they never appear in another member's alerts, since each member gets alerts for their own items and Shared ones.
- **Server unreachable:** the app says it couldn't load alerts and lets the user try again.

#### 1.2.6 F06: Household Members, Ownership, and Preferences

**Description:** This feature sets up the household and keeps track of who owns what. On first login, a user either creates a household, which gives them an invite code, or joins their roommates' household with that code. Each member also saves their dietary restrictions and disliked ingredients, which every AI feature respects. Every item is tagged with its owner, so the inventory can be filtered by owner.

**User Interaction:** After registering, the user enters their name and then chooses "Create a household" or "Join with a code." The Household page shows all members, the invite code with a copy button, and a "My preferences" section. There, the user ticks dietary restrictions from a fixed list (vegetarian, vegan, halal, gluten-free, dairy-free, nut-free) and types any disliked ingredients. On the Inventory page, an owner filter shows only one member's items or only Shared ones. In the CLI, this is done through `fridgemate household create`, `join`, and `show`, and `fridgemate prefs set`.

**Input:**
- The user's name
- A household name when creating, or an invite code when joining
- Dietary restrictions and disliked ingredients
- An owner to filter by on the Inventory page

**Output:** A household with its members and invite code, saved preferences, and a filtered inventory list.

**AI Involvement:** Deterministic. The preferences are used by the AI features (F07, F10, F13), but this feature itself has no AI.

**Expected Workflow:**
1. On first login, the user enters their name.
2. If they create a household, the server makes one with a unique random invite code. If they join, the server finds the household by its code and adds them as a member.
3. The user lands on the Inventory page of their household.
4. When the user saves preferences, they are stored with their account and used by every AI feature from then on.
5. When the user picks an owner filter, the inventory list shows only that owner's items.

**Error/Alternative Cases:**
- **Wrong invite code:** the app says no household was found with that code.
- **Already in a household:** each member belongs to one household, so the app says they are already a member. Switching households is not supported in this version.
- **Guessing codes:** invite codes are long and random, so they can't realistically be guessed.
- **Unusual disliked ingredient:** it is still saved as typed, and the AI treats it as something to avoid.

#### 1.2.7 F07: Constraint-Based Recipe Agent

**Description:** This is the main AI agent in Fridgemate. The user picks what kind of meal they want, and the agent finds recipes that fit those choices and can be made with the food they actually have. It only uses the user's own items and Shared items, never a roommate's food or anything expired, and it puts items that expire soon or were offered by roommates first. Every recipe is checked against the real stock before it is shown. Since the recipe database doesn't include cooking times or meal weights, the AI estimates both, and the app labels them as estimates.

**User Interaction:** On the Recipes page, the user picks from four dropdowns, each of which also has a "Let AI decide" option:

| Option | Choices |
| --- | --- |
| Cuisine | A list from the recipe database, such as Italian, Indian, or Chinese |
| Cooking time | Under 15, 15 to 30, 30 to 60, or over 60 minutes |
| Meal weight | Light, Medium, or Heavy |
| Servings | A number from 1 to 10 |

After pressing "Get recipes," the user sees up to 5 recipe cards. Each card shows the name, cuisine, estimated time and weight, which fridge items it uses (with expiring ones highlighted), and any missing ingredients. Recipes the AI wrote itself are labeled "AI-generated." Each card has a "Why this recipe?" button, a "Cook this" button (F09), and an "Add missing to shopping list" button (F11). In the CLI, the same search is `fridgemate recipes suggest --cuisine Italian --time 15-30 --weight light --servings 2`.

**Input:**
- The four option choices
- The user's own items and Shared items, gathered automatically
- The user's dietary restrictions and dislikes

**Output:** Up to 5 ranked recipes, each with its estimated time and weight, the items it uses, any missing ingredients, and a short explanation of why it was chosen. For any option set to "Let AI decide," the explanation also says what the AI chose and why.

**AI Involvement:** AI agent. The agent works in several steps and uses tools for the inventory, the recipe search, and the stock check. Rules like ownership and expiry are applied by regular code before the LLM sees any items.

**Expected Workflow:**
1. The user picks the options and presses "Get recipes."
2. The agent collects the user's usable items. Roommates' items and expired items are filtered out by regular code at this step.
3. The usable items are ranked by urgency, with expiring and offered items first.
4. The agent searches the recipe database using the most urgent ingredients, one at a time, and merges the results. If a cuisine was chosen, it searches within that cuisine.
5. The LLM estimates the cooking time and meal weight for each candidate, removes ones that don't fit the options or preferences, and makes a choice for any "Let AI decide" option.
6. Each remaining recipe is checked against the real stock, and missing ingredients are handled by F08.
7. If too few recipes fit, the agent writes one itself, labels it AI-generated, and checks it against the stock like the others.
8. The recipes are ranked by how many expiring items they use, how few ingredients are missing, and how well they fit the options.
9. The top results are shown, along with the explanation for each one.

**Error/Alternative Cases:**
- **No usable ingredients:** the agent says so and suggests the Quick Finder (F10) or the shopping list (F11).
- **No recipe fits every option:** the agent shows the closest matches and clearly says which option couldn't be met, for example "Nothing fits under 15 minutes." It never ignores an option silently.
- **Recipe database unavailable:** the agent says so and uses only AI-generated recipes, which are labeled and checked against the stock.
- **LLM unavailable:** the agent can't run, so the app shows a message and asks the user to try again shortly.
- **Malformed AI answer:** the server retries once, then shows an error.
- **Step limit reached:** the agent stops after 6 tool steps and returns what it has found so far, with a note.
- **Conflict with preferences:** recipes with a restricted or disliked ingredient are removed, even if they match everything else.

#### 1.2.8 F08: Missing-Ingredient Detection and Substitution

**Description:** For every recipe the agent suggests, this feature checks which ingredients the user has, which they have too little of, and which are missing. For missing ingredients, it suggests substitutes from what the user already has, such as using yogurt instead of sour cream. Anything without a good substitute can be added to the shopping list.

**User Interaction:** Each recipe card from F07 or F10 has a "You have" section and a "Missing" section. Each missing ingredient shows a suggestion like "Use yogurt instead?" with an Accept button, plus an "Add to shopping list" button. In the CLI, the recipe output lists missing ingredients and substitutes under each recipe.

**Input:**
- The recipe's ingredients and amounts
- The user's usable stock (their own items and Shared items that aren't expired)
- The user's dietary restrictions and dislikes

**Output:** Each ingredient marked as available, short, or missing, plus substitute suggestions for missing ones.

**AI Involvement:** Hybrid. Finding what is missing is deterministic: regular code compares amounts after converting units. Suggesting substitutes uses the LLM, and every suggestion is then checked by regular code.

**Expected Workflow:**
1. The agent passes a candidate recipe to the stock check.
2. Each ingredient is matched to the user's items, units are converted, and amounts are compared.
3. Ingredients that are short or missing are marked.
4. The LLM suggests substitutes, choosing only from the user's list of usable items.
5. Each suggestion is checked: it must be in stock, not expired, not a roommate's, and allowed by the user's preferences.
6. The results are shown on the recipe card.

**Error/Alternative Cases:**
- **Units that can't be converted:** for an amount like "a pinch," the ingredient is marked "check amount" instead of missing.
- **Different names for the same thing:** names like "scallion" and "green onion" are matched through a small list of common synonyms. If they still don't match, the ingredient shows as missing.
- **No good substitute:** the app says there's no substitute in stock and offers the shopping list button.
- **Invalid suggestion:** if the LLM suggests something the user doesn't have, it is dropped and never shown.

#### 1.2.9 F09: Cook Recipe

**Description:** When the user cooks a recipe, this feature subtracts the ingredients they used from the inventory, converting units where needed. For example, it can take 2 cloves from 1 bulb of garlic. If there are leftovers, they are added as a new item with their own expiry date. Cooking can be undone if the user made a mistake.

**User Interaction:** Pressing "Cook this" on a recipe card opens a confirmation screen. It shows each ingredient, how much will be taken, and which item it comes from. The user can adjust amounts, for example if they used less, and can turn on "Any leftovers?" to set the number of portions and where they're stored. After confirming, a message appears with an Undo button. In the CLI, the same action is `fridgemate cook <recipe-id> --servings 2 --leftovers 2`.

**Input:**
- The recipe and number of servings
- The amount used of each ingredient, which defaults to the recipe's amounts
- Leftovers (optional): the number of portions and the location

**Output:** Updated quantities in the inventory, with used-up items removed, any leftovers added as a new item owned by the user, and a short summary.

**AI Involvement:** Deterministic. The only AI involved is F04's expiry estimate for the leftovers.

**Expected Workflow:**
1. The user presses "Cook this" and reviews the amounts.
2. The server checks that every item still exists and has enough left.
3. The amounts are subtracted, with units converted where needed.
4. Items that reach zero are removed from the inventory.
5. Leftovers, if any, are added as a new item with an expiry estimate from F04.
6. The whole action is saved as one command in the user's undo history, and the alerts and shopping list are updated.
7. The page shows the summary with an Undo button.

**Error/Alternative Cases:**
- **Not enough stock:** something changed since the recipe was suggested. The app shows which items are short, and the user can adjust the amounts or cancel.
- **Units that can't be converted:** the user enters the amount in the item's own unit.
- **Item removed:** a roommate removed an item a moment earlier. The app says so and refreshes the screen.
- **Roommate's item:** a roommate's item can't be used, since only the user's own items and Shared items can be taken.
- **Undo:** pressing Undo restores every quantity and removes the leftovers item.

#### 1.2.10 F10: Quick Recipe Finder

**Description:** Sometimes the user wants recipe ideas for food that isn't in the app, for example while shopping or at a friend's place. The Quick Finder lets them type a list of ingredients and get recipes, with the same four options as F07. It uses the same agent, but takes ingredients from the typed list instead of the inventory. Since the typed food isn't tracked, there is no "Cook this" button here.

**User Interaction:** On the Quick Finder page, the user types ingredients one at a time, pressing Enter after each, picks the same four options as F07, and presses "Find recipes." The results look like F07's recipe cards, with missing ingredients and the "Why this recipe?" button, but without "Cook this." In the CLI, the same search is `fridgemate recipes find "chicken, rice, spinach" --time 15-30`.

**Input:**
- A typed list of at least one ingredient
- The four option choices
- The user's dietary restrictions and dislikes

**Output:** Up to 5 ranked recipes with estimates, missing ingredients, and explanations.

**AI Involvement:** AI. The same agent as F07 runs the same steps, with the typed list as its ingredient source.

**Expected Workflow:**
1. The user types ingredients, picks options, and presses "Find recipes."
2. The server cleans the list by trimming spaces and removing duplicates.
3. The agent searches the recipe database, estimates time and weight, and filters by the options and preferences.
4. Each recipe is checked against the typed list, and missing ingredients are handled by F08.
5. If too few recipes fit, the agent writes one, labels it AI-generated, and checks it the same way.
6. The results are shown.

**Error/Alternative Cases:**
- **Empty list:** the "Find recipes" button stays disabled until at least one ingredient is added.
- **Unrecognized entries:** entries that aren't food, like "asdf," are ignored, and the app says which ones it skipped.
- **Hidden instructions:** typed text that tries to give the AI instructions is treated as an ordinary ingredient name and has no effect.
- **Service failures:** if the recipe database or the LLM is unavailable, the app behaves the same way as in F07.

#### 1.2.11 F11: Shopping List Generation

**Description:** This feature builds each member's shopping list automatically. Missing ingredients from recipes and meal plans can be added with one click, and items that are running low are added on their own. Duplicates are merged, so "200 g flour" and "1 kg flour" become "1.2 kg flour." The list is grouped by store section, such as produce or dairy, to make shopping faster.

**User Interaction:** The Shopping List page shows the list grouped by store section, with a checkbox and quantity for each item. Each item also shows why it's there, such as "for Butter Chicken" or "running low." The user can add items by hand and clear checked ones. Shared items that run low appear on every member's list under a Shared heading. In the CLI, the list is managed with `fridgemate shopping list`, `add`, and `check`.

**Input:**
- Missing ingredients sent from F07, F08, F10, or F13
- Items that run low, which are detected automatically
- Items the user adds by hand

**Output:** A merged shopping list grouped by store section.

**AI Involvement:** Hybrid. The LLM matches names that mean the same thing and sorts items into store sections. Merging amounts and detecting low stock are deterministic.

**Expected Workflow:**
1. An item arrives from a recipe, from a low-stock check, or from the user.
2. An item counts as running low when its quantity falls to a quarter of the amount first added. When that happens, it is added to the list automatically.
3. The LLM matches the name to any similar item already on the list and picks a store section.
4. Amounts are converted to the same unit and merged.
5. The updated list is shown.
6. When the user checks items off, they are removed from the list. The user then adds the groceries to the inventory through F01 or F03.

**Error/Alternative Cases:**
- **Units that can't be merged:** for something like "2 cans" and "400 g," both stay on the list as separate lines under the same item.
- **AI unavailable:** only items with exactly the same name are merged, and the list isn't grouped by section.
- **Already in stock:** an ingredient the user already has enough of is not added.
- **Duplicate typed by hand:** it is merged with the existing item.

#### 1.2.12 F12: Natural-Language Fridge Commands

**Description:** This feature lets the user update the inventory by typing in plain English. For example, "I finished the milk, add 6 eggs, and move the chicken to the freezer" becomes three changes: remove the milk, add the eggs, and update the chicken's location. The agent shows these changes for the user to confirm before anything happens. If a request is unclear, it asks a follow-up question, and it remembers the recent conversation, so "actually, make that 12" works.

**User Interaction:** On the Chat page, the user types a message. The agent replies with a card listing the proposed changes, with Confirm and Cancel buttons. After confirming, an Undo button appears. In the CLI, the same action is `fridgemate do "I finished the milk"`, which prints the proposed changes and asks for yes or no.

**Input:**
- The user's message
- The user's own items and Shared items
- The recent conversation

**Output:** A card of proposed changes or a follow-up question. After confirming, the updated inventory and a short summary.

**AI Involvement:** AI. The agent uses tools to look up items and turns the message into proposed changes. Every change is checked by regular code before it is shown.

**Expected Workflow:**
1. The user types a message.
2. The agent looks up the items the message mentions, using a tool.
3. The LLM turns the message into a list of proposed changes in a fixed format.
4. Each change is checked: the item must exist, the user must be allowed to change it, the quantity must be valid, and the unit must be supported.
5. The proposed changes are shown on a card.
6. When the user confirms, each change is carried out as a command and added to the undo history.
7. The conversation is saved, so follow-up messages can refer to earlier ones.

**Error/Alternative Cases:**
- **Unclear item:** "the milk" matches two milk items, so the agent asks which one instead of guessing.
- **Roommate's item:** the agent explains that it can't change someone else's item and leaves that change out.
- **Unsupported request:** for a request like "order a pizza," the agent explains what it can do.
- **Invalid quantity:** for something like "add -3 eggs," the agent asks the user to correct it.
- **Partly understood:** the agent proposes the parts it understood and asks about the rest.
- **LLM unavailable:** the app suggests using the Inventory page instead.
- **Cancel:** nothing changes.

#### 1.2.13 F13: Waste-Rescue Meal Plan

**Description:** This feature plans the user's meals for the next 3 to 5 days, with the main goal of using up food before it expires. It assigns each expiring item to a day before its expiry date and builds the plan without repeating any dish. It also checks the whole plan against the stock, so the same eggs aren't counted twice. If something changes later, for example an item gets eaten or claimed by a roommate, the plan is marked as needing an update and can be re-planned.

**User Interaction:** On the Meal Plan page, the user chooses the number of days (3, 4, or 5), meals per day (1 or 2), and the maximum cooking time per meal, then presses "Plan my meals." The plan appears as a calendar, with one card per meal showing the recipe and the items it uses, with expiring ones highlighted. Each card has a "Cook this" button (F09) and a "Swap" button, and the page has an "Add missing to shopping list" button. If the plan becomes outdated, a banner offers a "Re-plan" button. In the CLI, the same action is `fridgemate plan --days 4`.

**Input:**
- The number of days, meals per day, and maximum cooking time
- The user's usable items and preferences
- The existing plan, when re-planning

**Output:** A saved meal plan with a recipe for each meal, a list of missing ingredients, and a short explanation for each day.

**AI Involvement:** AI agent. The agent plans across several days, uses tools for the inventory and recipe search, and re-plans when something conflicts.

**Expected Workflow:**
1. The user picks the options and presses "Plan my meals."
2. The agent collects the user's usable items and sorts them by expiry date.
3. Each expiring item is assigned to a day before it expires.
4. The agent searches for recipes that use each day's assigned items and estimates their cooking times.
5. It builds the plan and checks it: the total amounts across all days can't exceed the stock, and no dish can repeat.
6. If a check fails, the agent re-plans only the affected days.
7. The plan is saved and shown.
8. Each time the plan is opened, it is checked against the current stock. If something no longer fits, the banner appears, and "Re-plan" changes only the affected meals.

**Error/Alternative Cases:**
- **Not enough food:** the agent plans as many meals as it can, says which days are missing, and offers the shopping list.
- **Not enough different recipes:** the agent writes new ones, labeled AI-generated and checked against the stock.
- **Service failures:** if the recipe database or LLM fails partway, the agent returns the days it has planned and says which are missing.
- **Step limit reached:** the agent returns its best partial plan with a note.
- **Item expires before its day:** the plan is marked as needing an update.

#### 1.2.14 F14: Shared Grocery Cost Split

**Description:** When roommates buy groceries for everyone, it's easy to lose track of who paid for what. This feature splits the cost of Shared items equally among household members and shows who owes whom. It then works out the fewest payments needed to settle up. Items offered through F15 are free and are not counted.

**User Interaction:** On the Cost Split page, the user picks a period, with the current month as the default. The page shows a table of Shared purchases with the item, price, who paid, and date. Below it, a summary shows how much each member paid, their share, and their balance. A list of suggested payments, such as "Sam pays you $12.40," comes with a "Mark as paid" button. In the CLI, the same summary is `fridgemate costs --month 2026-10`.

**Input:**
- Shared items with a price and payer within the chosen period
- The household's members
- Payments already marked as paid

**Output:** Each member's balance and a short list of suggested payments.

**AI Involvement:** Deterministic. Everything is a calculation with one correct answer.

**Expected Workflow:**
1. The user opens the page and picks a period.
2. The server collects the Shared items in that period that have a price, leaving out items offered through F15.
3. Each item's cost is split equally among the household's current members.
4. Each member's balance is worked out as what they paid, minus their share, adjusted for payments already made.
5. The fewest payments are found by matching the member who owes the most with the member who is owed the most, and repeating until everyone is settled.
6. The summary and payments are shown.
7. When "Mark as paid" is pressed, the payment is recorded and the balances are recalculated.

**Error/Alternative Cases:**
- **Missing price or payer:** the item is listed under "Missing price" with an Edit link and left out of the split until it's fixed.
- **Only one member:** the page says there's nothing to split.
- **Rounding:** cents that don't divide evenly go to the payer, so the totals always match exactly.
- **Marked by mistake:** a recorded payment can be removed, and the balances are recalculated.

#### 1.2.15 F15: Share Before It Spoils

**Description:** This feature turns food that would be wasted into food a roommate can use. When one of the user's items is expiring soon and they know they won't use it, they can offer it to the household. The item becomes Shared, and every other member gets a notification. The first roommate to claim it becomes its new owner. The owner can withdraw the offer until someone claims it, and if nobody does, the item stays Shared until it expires. Offered items are free, so they are left out of the cost split.

**User Interaction:** Expiring items have an "Offer to household" button in the "Use it first" tab and in the item's details, where the user can also add a short note like "half a bag left." Other members see a notification under the bell icon, and the item is marked "Offered by Alex, expires in 2 days" with a Claim button. The owner sees a "Withdraw offer" button until it's claimed. In the CLI, this is done with `fridgemate offer <item>`, `fridgemate claim <item>`, and `fridgemate notifications`.

**Input:**
- The item being offered, plus an optional note
- A roommate's claim

**Output:** The item's new status, notifications for the other members, and, after a claim, the new owner. The person who offered the item is also told who claimed it.

**AI Involvement:** Deterministic.

**Expected Workflow:**
1. The owner presses "Offer to household."
2. The server checks that the user owns the item and that it is expiring soon, since only items in that state can be offered.
3. The item is marked as Shared and offered, as a command.
4. A notification is created for every other member of the household.
5. The other members see it the next time the app checks, which happens at least every minute.
6. When a roommate presses Claim, the item becomes theirs. This is a single database update that only succeeds if the item hasn't been claimed yet.
7. The person who offered the item is notified, for example "Sam claimed your spinach."

**Error/Alternative Cases:**
- **Not expiring soon:** the Offer button is disabled, with a note that items can be offered within 3 days of expiry.
- **Already expired:** the item can't be offered.
- **Two claims at once:** the first claim wins, and the second person sees "Already claimed by Sam."
- **Withdraw after a claim:** this isn't possible, since a claim is final. The new owner can offer it again if they change their mind.
- **Expires while offered:** the offer closes, the notification is removed, and the item shows as Expired.
- **No roommates:** if the user is the only member, offering is disabled.

#### 1.2.16 Supporting Functionality: Accounts (not counted as a feature)

These functions are needed for the app to know who is using it, but the instructions say login and change password don't count as features, so they are listed separately. All of them are handled by Auth0, which means Fridgemate never sees or stores passwords.

- **Register:** the user signs up with their email and password on Auth0's page and confirms their email. On first login, Fridgemate asks for their name and then for a household (F06).
- **Log in and log out:** the web app sends the user to Auth0's login page and back. The CLI uses `fridgemate login`, which shows a short code to confirm in the browser. Both keep the user logged in until they log out.
- **Change password:** the user presses "Change password" on the Household page, or runs `fridgemate change-password`, and Auth0 emails them a reset link.

**Error/Alternative Cases:**
- **Wrong email or password:** Auth0 shows an error without revealing which one was wrong.
- **Email already registered:** Auth0 asks the user to log in instead.
- **Session expired:** the app sends the user back to the login page, and nothing they saved is lost.

## 3. Class Diagram and Design Patterns (Task 2.1)

## 4. Use Cases (Task 2.2)

## 5. Sequence Diagrams (Task 2.3)

## 6. Traceability Table (Task 3)

## 7. Feature Implementation Explanations (Task 4)
