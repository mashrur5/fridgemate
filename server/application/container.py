"""Composition root: builds every object once and wires observers, strategies and agents together."""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from server.agent.conversation_memory import ConversationMemory
from server.agent.fridge_command_agent import FridgeCommandAgent
from server.agent.ingredient_source import FridgeIngredientSource
from server.agent.llm_strategies import LLMExpiryEstimator, LLMPlacementStrategy
from server.agent.meal_plan_agent import MealPlanAgent
from server.agent.receipt_parser import ReceiptParser
from server.agent.recipe_agent import RecipeAgent
from server.application.facade import FridgemateFacade
from server.config import Config
from server.domain.commands import CommandHistory
from server.domain.services import (
    ExpiryAlertNotifier, ExpiryService, InventoryService, PlacementService, RuleBasedExpiryEstimator,
    RuleBasedPlacementStrategy,
)
from server.domain.services.account_service import AccountService
from server.domain.services.cooking_service import CookingService
from server.domain.services.cost_split_service import CostSplitService
from server.domain.services.household_service import HouseholdService
from server.domain.services.notification_service import HouseholdNotifier, NotificationService
from server.domain.services.shopping_list_service import ShoppingListService
from server.domain.services.stock_validator import StockValidator
from server.domain.services.unit_converter import UnitConverter
from server.infrastructure.llm import LLMClient
from server.infrastructure.llm.factory import LLMClientFactory
from server.infrastructure.persistence import (
    InMemoryAccountRepository, InMemoryCostRepository, InMemoryHouseholdRepository, InMemoryItemRepository,
    InMemoryMealPlanRepository, InMemoryMemberRepository, InMemoryNotificationRepository,
    InMemoryShoppingListRepository,
)
from server.infrastructure.persistence.sqlite import (
    Database, SqliteAccountRepository, SqliteCostRepository, SqliteHouseholdRepository, SqliteItemRepository,
    SqliteMealPlanRepository, SqliteMemberRepository, SqliteNotificationRepository, SqliteShoppingListRepository,
)
from server.infrastructure.recipes import MealDBRecipeSource, RecipeSource


def build_facade(config: Config, *, llm: Optional[LLMClient] = None, recipes: Optional[RecipeSource] = None,
                 in_memory: bool = False, today: Callable[[], date] = date.today) -> FridgemateFacade:
    if in_memory:
        members, households, accounts = (InMemoryMemberRepository(), InMemoryHouseholdRepository(),
                                         InMemoryAccountRepository())
        items, shopping_repo, costs_repo = InMemoryItemRepository(), InMemoryShoppingListRepository(), InMemoryCostRepository()
        notes_repo, plans_repo = InMemoryNotificationRepository(), InMemoryMealPlanRepository()
    else:
        db = Database(config.database_path)
        members, households, accounts = SqliteMemberRepository(db), SqliteHouseholdRepository(db), SqliteAccountRepository(db)
        items, shopping_repo, costs_repo = (SqliteItemRepository(db, members), SqliteShoppingListRepository(db),
                                            SqliteCostRepository(db))
        notes_repo, plans_repo = SqliteNotificationRepository(db), SqliteMealPlanRepository(db)

    llm = llm or LLMClientFactory(config).create_client()  # Factory Method
    recipes = recipes or MealDBRecipeSource(config.mealdb_api_key)
    converter = UnitConverter()
    validator = StockValidator(converter)

    inventory = InventoryService(items, today=today)
    notifications = NotificationService(notes_repo)
    alerts = ExpiryAlertNotifier(inventory)
    shopping = ShoppingListService(shopping_repo, converter)
    costs = CostSplitService(costs_repo, members, items, today=today)
    for observer in (alerts, shopping, HouseholdNotifier(notifications, members, today=today), costs):
        inventory.attach(observer)  # Observer pattern

    placement = PlacementService(LLMPlacementStrategy(llm), RuleBasedPlacementStrategy())  # Strategy pattern
    expiry = ExpiryService(LLMExpiryEstimator(llm), RuleBasedExpiryEstimator())
    recipe_agent = RecipeAgent(llm, recipes, validator, converter, today=today)

    return FridgemateFacade(
        accounts=AccountService(accounts, members, households),
        households=HouseholdService(households, members),
        inventory=inventory, history=CommandHistory(), placement=placement, expiry=expiry, alerts=alerts,
        notifications=notifications, shopping=shopping, costs=costs,
        cooking=CookingService(inventory, validator, expiry, today=today),
        recipe_agent=recipe_agent,
        meal_planner=MealPlanAgent(llm, recipe_agent, FridgeIngredientSource(inventory), plans_repo, today=today),
        command_agent=FridgeCommandAgent(llm, inventory, ConversationMemory(), converter, today=today),
        receipts=ReceiptParser(llm, converter=converter), members=members, llm=llm, today=today)
