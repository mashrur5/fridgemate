"""Facade: the single entry point the API routers (and through them both clients) call."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

from server.agent.fridge_command_agent import CommandReply, FridgeCommandAgent
from server.agent.ingredient_source import FridgeIngredientSource, ManualIngredientSource
from server.agent.meal_plan_agent import MealPlanAgent
from server.agent.receipt_parser import ReceiptLine, ReceiptParser
from server.agent.recipe_agent import RecipeAgent, RecipeResult
from server.application.request_context import RequestContext
from server.domain.commands import (
    AddItemCommand, ClaimItemCommand, CommandHistory, CookRecipeCommand, OfferItemCommand, RemoveItemCommand,
    UpdateItemCommand,
)
from server.domain.errors import InvalidOperationError, NotFoundError
from server.domain.model import (
    CostSummary, FoodItem, Household, Location, MealPlan, Member, Notification, PlannedMeal, ProposedChanges,
    Quantity, Recipe, RecipeRequest, ShoppingList, ShoppingListItem,
)
from server.domain.services import ExpiryAlertNotifier, ExpiryService, InventoryService, PlacementService
from server.domain.services.account_service import AccountService
from server.domain.services.cooking_service import CookingService, Leftovers, Usage
from server.domain.services.cost_split_service import CostSplitService
from server.domain.services.household_service import HouseholdService
from server.domain.services.notification_service import NotificationService
from server.domain.services.shopping_list_service import ShoppingListService
from server.domain.services.stock_validator import CheckResult
from server.infrastructure.llm import LLMClient
from server.infrastructure.persistence import MemberRepository


@dataclass
class ItemInput:
    name: str
    amount: float
    unit: str
    location: Optional[str] = None  # None = "Suggest for me" (F02)
    expiry_date: Optional[date] = None  # None = estimate (F04)
    owner: str = "me"  # "me", "shared", or a member id
    price: Optional[Decimal] = None
    payer_id: Optional[UUID] = None


@dataclass
class AddResult:
    item: FoodItem
    location_note: Optional[str] = None  # e.g. "Freezer: keeps for months (AI)"
    expiry_note: Optional[str] = None


@dataclass
class CookPreview:
    recipe: Recipe
    check: CheckResult
    usages: list[Usage]


class FridgemateFacade:
    def __init__(self, *, accounts: AccountService, households: HouseholdService, inventory: InventoryService,
                 history: CommandHistory, placement: PlacementService, expiry: ExpiryService,
                 alerts: ExpiryAlertNotifier, notifications: NotificationService, shopping: ShoppingListService,
                 costs: CostSplitService, cooking: CookingService, recipe_agent: RecipeAgent,
                 meal_planner: MealPlanAgent, command_agent: FridgeCommandAgent, receipts: ReceiptParser,
                 members: MemberRepository, llm: LLMClient, today: Callable[[], date] = date.today) -> None:
        self.accounts, self.households, self.inventory, self.history = accounts, households, inventory, history
        self.placement, self.expiry, self.alerts, self.notifications = placement, expiry, alerts, notifications
        self.shopping, self.costs, self.cooking = shopping, costs, cooking
        self.recipe_agent, self.meal_planner, self.command_agent, self.receipts = (
            recipe_agent, meal_planner, command_agent, receipts)
        self.members, self.llm, self.today = members, llm, today

    # ---------- accounts (UC16) ----------

    def register(self, email: str, password: str, name: str) -> Member:
        return self.accounts.register(email, password, name)

    def login(self, email: str, password: str) -> str:
        return self.accounts.login(email, password)

    def logout(self, token: str) -> None:
        self.accounts.logout(token)

    def change_password(self, member: Member, old: str, new: str) -> None:
        self.accounts.change_password(member, old, new)

    def load_context(self, token: str) -> tuple[Member, Optional[Household]]:
        return self.accounts.load_context(token)

    # ---------- F06 household ----------

    def create_household(self, member: Member, name: str) -> Household:
        return self.households.create_household(member, name)

    def join_household(self, member: Member, code: str) -> Household:
        return self.households.join_household(member, code)

    def get_members(self, ctx: RequestContext) -> list[Member]:
        return self.households.get_members(ctx)

    def update_preferences(self, member: Member, restrictions: list[str], dislikes: list[str],
                           name: Optional[str] = None) -> Member:
        return self.households.update_preferences(member, restrictions, dislikes, name)

    # ---------- F01 / F02 / F04 inventory ----------

    def list_items(self, ctx: RequestContext, location: Optional[str] = None, owner: Optional[str] = None,
                   freshness: Optional[str] = None, query: Optional[str] = None) -> list[FoodItem]:
        items = self.inventory.get_items(ctx)
        if location:
            items = [i for i in items if i.location.value == location]
        if owner == "me":
            items = [i for i in items if i.owner and i.owner.id == ctx.member.id]
        elif owner == "shared":
            items = [i for i in items if i.is_shared()]
        elif owner == "offered":
            items = [i for i in items if i.is_offered]
        elif owner:
            items = [i for i in items if i.owner and str(i.owner.id) == owner]
        if freshness:
            items = [i for i in items if i.freshness_label().lower() == freshness.lower()]
        if query:
            items = [i for i in items if query.lower() in i.name.lower()]
        return items

    def suggest_location(self, name: str) -> tuple[Location, str, str]:
        return self.placement.suggest(name)

    def estimate_expiry(self, name: str, location: Location) -> tuple[date, str]:
        return self.expiry.estimate(name, location, self.today())

    def _owner(self, ctx: RequestContext, owner: str) -> Optional[Member]:
        if owner in ("me", "", None):
            return ctx.member
        if owner == "shared":
            return None
        member = next((m for m in self.get_members(ctx) if str(m.id) == owner), None)
        if member is None:
            raise NotFoundError("that member is not in your household")
        return member

    def _payer(self, ctx: RequestContext, payer_id: Optional[UUID]) -> Optional[Member]:
        if payer_id is None:
            return None
        payer = next((m for m in self.get_members(ctx) if m.id == payer_id), None)
        if payer is None:
            raise NotFoundError("the payer is not in your household")
        return payer

    def build_item(self, ctx: RequestContext, data: ItemInput) -> AddResult:
        """Fill in a missing location (F02) and expiry date (F04), then build the item."""
        location_note = expiry_note = None
        if data.location:
            location = Location(data.location.lower())
        else:
            location, reason, source = self.placement.suggest(data.name)
            location_note = f"{location.value.title()}: {reason} ({'AI' if source == 'ai' else 'rule table'})"
        estimated = data.expiry_date is None
        if estimated:
            expiry, source = self.expiry.estimate(data.name, location, self.today())
            expiry_note = f"Estimated {expiry.isoformat()} ({'AI' if source == 'ai' else 'rule table'})"
        else:
            expiry = data.expiry_date
            if expiry < self.today():
                expiry_note = "This date is in the past, so the item is saved as Expired."
        item = FoodItem(name=data.name.strip(), quantity=Quantity(data.amount, data.unit), location=location,
                        household_id=ctx.household.id, expiry_date=expiry, added_on=self.today(),
                        owner=self._owner(ctx, data.owner), expiry_estimated=estimated, price=data.price,
                        payer=self._payer(ctx, data.payer_id))
        return AddResult(item, location_note, expiry_note)

    def add_item(self, ctx: RequestContext, data: ItemInput) -> AddResult:
        result = self.build_item(ctx, data)
        self.history.run(ctx, AddItemCommand(self.inventory, ctx, result.item))
        return result

    def update_item(self, ctx: RequestContext, item_id: UUID, *, name: Optional[str] = None,
                    amount: Optional[float] = None, unit: Optional[str] = None, location: Optional[str] = None,
                    expiry_date: Optional[date] = None, owner: Optional[str] = None,
                    price: Optional[Decimal] = None, payer_id: Optional[UUID] = None) -> FoodItem:
        current = self.inventory.get_item(ctx, item_id)
        changed = copy.copy(current)
        if name is not None:
            if not name.strip():
                raise ValueError("item name cannot be empty")
            changed.name = name.strip()
        if amount is not None or unit is not None:
            new = Quantity(amount if amount is not None else current.quantity.amount, unit or current.quantity.unit)
            if new.amount <= 0:
                raise ValueError("quantity must be greater than 0")
            changed.quantity = new
            changed.original_amount = max(current.original_amount if new.unit == current.quantity.unit else 0,
                                          new.amount)
        if location is not None:
            changed.location = Location(location.lower())
        if expiry_date is not None:
            changed.expiry_date, changed.expiry_estimated = expiry_date, False
        if owner is not None:
            changed.owner = self._owner(ctx, owner)
        if price is not None:
            changed.price = price
        if payer_id is not None:
            changed.payer = self._payer(ctx, payer_id)
        self.history.run(ctx, UpdateItemCommand(self.inventory, ctx, changed))
        return self.inventory.get_item(ctx, item_id)

    def remove_item(self, ctx: RequestContext, item_id: UUID) -> None:
        self.history.run(ctx, RemoveItemCommand(self.inventory, ctx, item_id))

    def undo(self, ctx: RequestContext) -> Optional[str]:
        """Undo this member's last change. Returns what was undone, or None if there was nothing."""
        description = self.history.last_description(ctx)
        return description if self.history.undo_last(ctx) else None

    def last_action(self, ctx: RequestContext) -> Optional[str]:
        return self.history.last_description(ctx)

    # ---------- F05 alerts ----------

    def get_alerts(self, ctx: RequestContext) -> list[FoodItem]:
        return self.alerts.get_alerts(ctx)

    # ---------- F15 offer and claim ----------

    def offer_item(self, ctx: RequestContext, item_id: UUID, note: str = "") -> FoodItem:
        if len(self.get_members(ctx)) < 2:
            raise InvalidOperationError("there are no roommates to offer to yet")
        self.history.run(ctx, OfferItemCommand(self.inventory, ctx, item_id, note))
        return self.inventory.get_item(ctx, item_id)

    def claim_item(self, ctx: RequestContext, item_id: UUID) -> FoodItem:
        item = self.inventory.get_item(ctx, item_id)
        if not item.is_offered:
            owner = item.owner.name if item.owner else "someone"
            raise InvalidOperationError(f"already claimed by {owner}")
        command = ClaimItemCommand(self.inventory, ctx, item_id)
        self.history.run(ctx, command)
        if not command.succeeded:
            winner = self.inventory.get_item(ctx, item_id).owner
            raise InvalidOperationError(f"already claimed by {winner.name if winner else 'someone'}")
        return self.inventory.get_item(ctx, item_id)

    def get_notifications(self, member: Member) -> list[Notification]:
        return self.notifications.get_for(member)

    def mark_notifications_read(self, member: Member) -> None:
        self.notifications.mark_all_read(member)

    # ---------- F03 receipts ----------

    def parse_receipt_image(self, ctx: RequestContext, data: bytes, mime: str) -> list[AddResult]:
        return self._drafts(ctx, self.receipts.parse_image(data, mime))

    def parse_receipt_text(self, ctx: RequestContext, text: str) -> list[AddResult]:
        return self._drafts(ctx, self.receipts.parse_text(text))

    def _drafts(self, ctx: RequestContext, lines: list[ReceiptLine]) -> list[AddResult]:
        drafts = []
        for line in lines:
            draft = self.build_item(ctx, ItemInput(line.name, line.amount, line.unit, price=line.price))
            if line.unclear:
                draft.location_note = "Check this: the line was hard to read. " + (draft.location_note or "")
            drafts.append(draft)
        return drafts

    def save_receipt(self, ctx: RequestContext, items: list[ItemInput], payer_id: Optional[UUID]) -> list[FoodItem]:
        """Save the reviewed receipt items. Imports have no undo (Stage 1 F03)."""
        if not items:
            raise ValueError("there are no items to save")
        built = []
        for data in items:
            data.payer_id = payer_id if data.price is not None else None
            built.append(self.build_item(ctx, data).item)  # build all first, so one bad line saves nothing
        for item in built:
            self.inventory.add(ctx, item)
        return built

    # ---------- F07 / F08 / F10 recipes ----------

    def suggest_recipes(self, ctx: RequestContext, request: RecipeRequest) -> RecipeResult:
        return self.recipe_agent.suggest(ctx, request, FridgeIngredientSource(self.inventory))

    def find_recipes(self, ctx: RequestContext, ingredients: list[str], request: RecipeRequest) -> RecipeResult:
        source = ManualIngredientSource(ingredients)
        if not source.names:
            raise ValueError("add at least one ingredient")
        return self.recipe_agent.suggest(ctx, request, source)

    def get_recipe(self, recipe_id: str) -> Recipe:
        recipe = self.recipe_agent.find_recipe(recipe_id)
        if recipe is None:
            raise NotFoundError("recipe not found (AI-written recipes are forgotten when the server restarts)")
        return recipe

    def list_cuisines(self) -> list[str]:
        return self.recipe_agent.recipes.list_cuisines()

    def add_missing_to_shopping(self, ctx: RequestContext, recipe_id: str, servings: int = 2) -> list[ShoppingListItem]:
        recipe = self.get_recipe(recipe_id)
        preview = self.cook_preview(ctx, recipe_id, servings)
        added = []
        for c in preview.check.checks:
            if c.status in ("missing", "short"):
                qty = c.ingredient.quantity
                if qty is not None:
                    qty = Quantity(qty.amount * servings / max(recipe.servings, 1), qty.unit)
                added.append(self.shopping.add_item(ctx, c.ingredient.name, qty, f"for {recipe.name}"))
        return added

    # ---------- F09 cook ----------

    def cook_preview(self, ctx: RequestContext, recipe_id: str, servings: int = 2) -> CookPreview:
        recipe = self.get_recipe(recipe_id)
        check, usages = self.cooking.preview(ctx, recipe, servings / max(recipe.servings, 1))
        return CookPreview(recipe, check, usages)

    def cook(self, ctx: RequestContext, recipe_id: str, usages: list[Usage],
             leftovers: Optional[Leftovers] = None) -> str:
        recipe = self.get_recipe(recipe_id)
        if not usages and leftovers is None:
            raise ValueError("nothing to take from the inventory")
        self.history.run(ctx, CookRecipeCommand(self.inventory, self.cooking, ctx, recipe.name, usages, leftovers))
        return f"Cooked {recipe.name}: used {len(usages)} item(s)" + (
            f", added {leftovers.portions} leftover portion(s)" if leftovers else "")

    # ---------- F11 shopping ----------

    def get_shopping_list(self, ctx: RequestContext) -> ShoppingList:
        return self.shopping.get_list(ctx)

    def add_shopping_item(self, ctx: RequestContext, name: str, quantity: Optional[Quantity],
                          shared: bool = False) -> ShoppingListItem:
        return self.shopping.add_item(ctx, name, quantity, "added by hand", shared)

    def check_shopping_item(self, ctx: RequestContext, item_id: UUID, checked: bool) -> ShoppingListItem:
        return self.shopping.set_checked(ctx, item_id, checked)

    def remove_shopping_item(self, ctx: RequestContext, item_id: UUID) -> None:
        self.shopping.remove(ctx, item_id)

    def clear_checked(self, ctx: RequestContext) -> int:
        return self.shopping.clear_checked(ctx)

    # ---------- F12 natural-language commands ----------

    def chat(self, ctx: RequestContext, message: str) -> CommandReply:
        return self.command_agent.handle(ctx, message)

    def confirm_changes(self, ctx: RequestContext, proposal_id: UUID) -> list[str]:
        proposal = self.command_agent.take_pending(ctx, proposal_id)
        if proposal is None:
            raise NotFoundError("this proposal is no longer open")
        done = []
        for change in proposal.changes:
            try:
                self._apply_change(ctx, change)
                done.append(change.describe())
            except (InvalidOperationError, NotFoundError, ValueError) as e:
                done.append(f"Skipped '{change.describe()}': {e}")
        return done

    def cancel_changes(self, ctx: RequestContext, proposal_id: UUID) -> bool:
        return self.command_agent.take_pending(ctx, proposal_id) is not None

    def _apply_change(self, ctx: RequestContext, change) -> None:
        if change.op == "add":
            self.add_item(ctx, ItemInput(change.name, change.amount, change.unit, change.location,
                                         owner="shared" if change.owner == "shared" else "me"))
            return
        item = self.inventory.get_item(ctx, change.item_id)
        if change.op == "remove":
            self.remove_item(ctx, item.id)
        elif change.op == "move":
            self.update_item(ctx, item.id, location=change.location)
        elif change.op in ("use", "set"):
            qty = self.cooking.validator.converter.convert(Quantity(change.amount, change.unit or item.quantity.unit),
                                                           item.quantity.unit, item.name)
            if qty is None:
                raise ValueError(f"{item.name} is measured in {item.quantity.unit}")
            left = item.quantity.amount - qty.amount if change.op == "use" else qty.amount
            if left < -1e-9:
                raise InvalidOperationError(f"only {item.quantity.amount:g} {item.quantity.unit} left")
            if left <= 1e-9:
                self.remove_item(ctx, item.id)
            else:
                self.update_item(ctx, item.id, amount=left)

    # ---------- F13 meal plan ----------

    def plan_meals(self, ctx: RequestContext, days: int, meals_per_day: int = 1,
                   max_minutes: Optional[int] = None) -> MealPlan:
        return self.meal_planner.plan(ctx, days, meals_per_day, max_minutes)

    def get_meal_plan(self, ctx: RequestContext) -> tuple[Optional[MealPlan], list[PlannedMeal]]:
        plan = self.meal_planner.latest(ctx)
        return plan, (self.meal_planner.outdated_meals(ctx, plan) if plan else [])

    def replan_meals(self, ctx: RequestContext, max_minutes: Optional[int] = None) -> MealPlan:
        plan = self.meal_planner.latest(ctx)
        if plan is None:
            raise NotFoundError("there is no meal plan yet")
        return self.meal_planner.replan(ctx, plan, max_minutes)

    # ---------- F14 costs ----------

    def get_costs(self, ctx: RequestContext, month: Optional[str] = None) -> CostSummary:
        return self.costs.summarize(ctx, month)

    def missing_prices(self, ctx: RequestContext) -> list[FoodItem]:
        return self.costs.missing_price(ctx)

    def mark_paid(self, ctx: RequestContext, from_id: UUID, to_id: UUID, amount: Decimal):
        return self.costs.mark_paid(ctx, from_id, to_id, amount)

    def remove_payment(self, ctx: RequestContext, payment_id: UUID) -> None:
        self.costs.remove_payment(ctx, payment_id)

    # ---------- AI status ----------

    def ai_status(self) -> dict:
        u = self.llm.usage
        return {"provider": self.llm.name, "calls": u.calls, "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens}
