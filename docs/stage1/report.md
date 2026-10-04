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
- **Retrieval:-** Recipes come from TheMealDB, an external recipe database, so suggestions are based on real recipes.
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

## 2. Feature Specifications (Task 1.2)

## 3. Class Diagram and Design Patterns (Task 2.1)

## 4. Use Cases (Task 2.2)

## 5. Sequence Diagrams (Task 2.3)

## 6. Traceability Table (Task 3)

## 7. Feature Implementation Explanations (Task 4)
