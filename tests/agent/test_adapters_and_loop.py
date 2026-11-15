import json

import httpx
import pytest

from server.agent.agent_trace import AgentTrace
from server.agent.base_agent import AgentError, BaseAgent
from server.agent.llm_strategies import LLMExpiryEstimator, LLMPlacementStrategy
from server.agent.tools import Tool, ToolRegistry
from server.config import Config
from server.domain.model import Location
from server.domain.services import ExpiryService, PlacementService, RuleBasedExpiryEstimator, RuleBasedPlacementStrategy
from server.infrastructure.llm import LLMUnavailableError, Message, UnavailableLLMClient
from server.infrastructure.llm.factory import LLMClientFactory
from server.infrastructure.llm.gemini_client import GeminiClient
from server.infrastructure.llm.ollama_client import OllamaClient
from server.infrastructure.llm.retry_policy import RetryPolicy
from server.infrastructure.recipes import MealDBRecipeSource
from tests.conftest import TODAY
from tests.fakes import FakeLLMClient


def test_gemini_adapter_builds_request_and_reads_answer():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["key"] = str(request.url), request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}}],
                                         "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3}})

    client = GeminiClient("k", "gemini-test", http=httpx.Client(transport=httpx.MockTransport(handler)),
                          thinking_level="low")
    r = client.generate("sys", [Message("user", "hi")])
    assert r.text == '{"a": 1}' and client.usage.input_tokens == 7
    assert "gemini-test:generateContent" in seen["url"] and seen["key"] == "k"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["body"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_gemini_overload_is_retried_then_unavailable():
    calls = []
    client = GeminiClient("k", "m", http=httpx.Client(transport=httpx.MockTransport(
        lambda r: calls.append(1) or httpx.Response(503))), retry=RetryPolicy(3, sleep=lambda s: None))
    with pytest.raises(LLMUnavailableError):
        client.generate("s", [Message("user", "x")])
    assert len(calls) == 3


def test_gemini_all_quotas_used_up():
    client = GeminiClient("k", "m", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429))),
                          fallback_models=["n"])
    with pytest.raises(LLMUnavailableError, match="quota"):
        client.generate("s", [Message("user", "x")])


def test_gemini_moves_to_fallback_model_when_quota_is_used_up():
    calls = []

    def handler(request: httpx.Request):
        model = request.url.path.split("/")[-1].split(":")[0]
        calls.append(model)
        if model == "main":
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    client = GeminiClient("k", "main", http=httpx.Client(transport=httpx.MockTransport(handler)),
                          fallback_models=["backup"], retry=RetryPolicy(3, sleep=lambda s: None), clock=lambda: 0.0)
    client.generate("s", [Message("user", "x")])
    client.generate("s", [Message("user", "y")])
    assert calls == ["main", "backup", "backup"]  # no retries on 429, and the used-up model is skipped
    assert client.last_model == "backup"


def test_factory_picks_client_from_config():
    assert isinstance(LLMClientFactory(Config(gemini_api_key="x")).create_client(), GeminiClient)
    assert isinstance(LLMClientFactory(Config(llm_provider="ollama")).create_client(), OllamaClient)
    assert isinstance(LLMClientFactory(Config(gemini_api_key="")).create_client(), UnavailableLLMClient)


def test_mealdb_adapter_maps_recipes():
    def handler(request: httpx.Request):
        if request.url.path.endswith("filter.php"):
            return httpx.Response(200, json={"meals": [{"idMeal": "1", "strMeal": "Spinach Pie", "strMealThumb": ""}]})
        return httpx.Response(200, json={"meals": [{"idMeal": "1", "strMeal": "Spinach Pie", "strArea": "Greek",
                                                    "strIngredient1": "Spinach", "strMeasure1": "200g",
                                                    "strIngredient2": "Salt", "strMeasure2": "pinch",
                                                    "strIngredient3": "", "strInstructions": "Bake."}]})
    src = MealDBRecipeSource(http=httpx.Client(transport=httpx.MockTransport(handler)))
    assert src.search_by_ingredient("spinach")[0].name == "Spinach Pie"
    r = src.get_recipe("1")
    assert r.cuisine == "Greek" and r.ingredients[0].quantity.amount == 200 and r.ingredients[1].quantity is None


class Echo(Tool):
    name, description = "echo", "echo back"

    def run(self, ctx, args):
        return {"echo": args}


def test_tool_loop_calls_tools_then_finishes(ctx_alice):
    llm = FakeLLMClient([{"thought": "look", "tool": "echo", "args": {"x": 1}},
                         "not json at all",  # G5: invalid answer, retried once
                         {"thought": "done", "final": {"answer": 42}}])
    trace = AgentTrace("test")
    result = BaseAgent(llm).run_tool_loop(ctx_alice, "sys", [Message("user", "go")], ToolRegistry([Echo()]), trace)
    assert result.final == {"answer": 42} and result.steps == 1 and not result.hit_limit
    assert trace.tool_calls() == ["echo"] and [s.kind for s in trace.steps] == ["tool", "retry", "final"]
    assert "TOOL RESULT (echo)" in llm.calls[1][1][-1].text


def test_tool_loop_stops_at_step_limit(ctx_alice):
    llm = FakeLLMClient([{"tool": "echo", "args": {}}] * 6 + [{"final": {"partial": True}}])
    result = BaseAgent(llm).run_tool_loop(ctx_alice, "s", [Message("user", "go")], ToolRegistry([Echo()]),
                                          AgentTrace("t"))
    assert result.hit_limit and result.steps == 6 and result.final == {"partial": True}
    assert "STEP LIMIT" in llm.calls[-1][1][-1].text


def test_tool_loop_gives_up_after_two_bad_answers(ctx_alice):
    with pytest.raises(AgentError):
        BaseAgent(FakeLLMClient(["bad", "{\"nope\": 1}"])).run_tool_loop(
            ctx_alice, "s", [Message("user", "go")], ToolRegistry([]), AgentTrace("t"))


def test_unknown_tool_is_reported_back_to_the_llm(ctx_alice):
    llm = FakeLLMClient([{"tool": "hack_db", "args": {}}, {"final": {}}])
    BaseAgent(llm).run_tool_loop(ctx_alice, "s", [Message("user", "go")], ToolRegistry([Echo()]), AgentTrace("t"))
    assert "unknown tool" in llm.calls[1][1][-1].text


def test_llm_strategies_with_rule_fallback():
    placement = PlacementService(LLMPlacementStrategy(FakeLLMClient([{"location": "freezer", "reason": "lasts months"}])),
                                 RuleBasedPlacementStrategy())
    assert placement.suggest("ground beef") == (Location.FREEZER, "lasts months", "ai")
    broken = PlacementService(LLMPlacementStrategy(FakeLLMClient([{"location": "garage", "reason": "x"}] * 2)),
                              RuleBasedPlacementStrategy())
    assert broken.suggest("milk")[0] == Location.FRIDGE and broken.suggest("milk")[2] == "rules"
    expiry = ExpiryService(LLMExpiryEstimator(FakeLLMClient([{"days": 5}])), RuleBasedExpiryEstimator())
    assert expiry.estimate("milk", Location.FRIDGE, TODAY)[1] == "ai"
    offline = ExpiryService(LLMExpiryEstimator(UnavailableLLMClient("off")), RuleBasedExpiryEstimator())
    assert offline.estimate("milk", Location.FRIDGE, TODAY)[1] == "rules"
