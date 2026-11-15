"""Builds the Stage 2 class diagrams (Graphviz) from the implemented code structure.

Run: python docs/stage2/diagrams/make_diagrams.py   (needs Graphviz `dot`)"""
import html
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
IFACE, PAT = "#eef4ff", "#fff7e6"
HEAD = """  graph [fontname="Helvetica", fontsize=12, nodesep=0.4, ranksep=0.55, splines=ortho, bgcolor=white, pad=0.25];
  node [shape=plain, fontname="Helvetica", fontsize=11];
  edge [fontname="Helvetica", fontsize=10, arrowsize=0.9];"""


def cls(name, members=(), stereo=None, abstract=False, fill="#ffffff"):
    title = "<BR/>".join(html.escape(p) for p in name.split("\n"))
    title = f"<I>{title}</I>" if abstract else f"<B>{title}</B>"
    st = f'<TR><TD><FONT POINT-SIZE="9">«{html.escape(stereo)}»</FONT></TD></TR>' if stereo else ""
    rows = "".join(f'<TR><TD ALIGN="LEFT">{html.escape(m)}</TD></TR>' for m in members)
    body = (f'<TR><TD BORDER="1" SIDES="T" ALIGN="LEFT"><TABLE BORDER="0" CELLSPACING="0" CELLPADDING="1">{rows}'
            f'</TABLE></TD></TR>') if members else ""
    return f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{fill}">{st}<TR><TD>{title}</TD></TR>{body}</TABLE>>'


REAL = 'arrowhead=empty'                 # generalization
IMPL = 'arrowhead=empty, style=dashed'   # realization
DEP = 'style=dashed'                      # dependency


def write(name, title, nodes, edges, rankdir="BT", same_rank=()):
    out = ["digraph G {", HEAD, f'  rankdir={rankdir}; labelloc=t; label=<<B>{html.escape(title)}</B>>;']
    out += [f"  {k} [label={v}];" for k, v in nodes.items()]
    out += [f"  {{rank=same; {' '.join(r)}}}" for r in same_rank]
    out += [f"  {e};" for e in edges]
    out.append("}")
    dot = HERE / f"{name}.dot"
    dot.write_text("\n".join(out))
    subprocess.run(["dot", "-Tpng", "-Gdpi=150", str(dot), "-o", str(HERE / f"{name}.png")], check=True)


# ---- State ----
write("pattern-state", "State: FoodItem freshness", {
    "item": cls("FoodItem", ["- _state: FreshnessState", "+ refresh_state(today)", "+ can_use_in_recipe(): bool",
                             "+ can_offer(): bool", "+ alert_priority(): int", "+ freshness_label(): str"], "Context"),
    "fs": cls("FreshnessState", ["+ can_use_in_recipe()", "+ can_offer()", "+ alert_priority()", "+ label()",
                                 "+ for_dates(expiry, today) {static}"], "State", True, IFACE),
    "a": cls("FreshState", ["recipe: yes, offer: no"]), "b": cls("ExpiringSoonState", ["recipe: yes, offer: yes"]),
    "c": cls("ExpiredState", ["recipe: no, offer: no"]),
}, ["a -> fs [%s]" % REAL, "b -> fs [%s]" % REAL, "c -> fs [%s]" % REAL,
    'item -> fs [arrowhead=open, arrowtail=diamond, dir=both, xlabel=" 1"]'], rankdir="BT", same_rank=[("item", "fs")])

# ---- Observer ----
write("pattern-observer", "Observer: reacting to inventory changes", {
    "inv": cls("InventoryService", ["- observers: list[InventoryObserver]", "+ attach(o) / detach(o)",
                                    "+ notify_observers(item, change)", "+ add / update / remove / deduct / claim"],
               "Subject", fill=PAT),
    "obs": cls("InventoryObserver", ["+ update(item, change)"], "Observer", True, IFACE),
    "a": cls("ExpiryAlertNotifier", ["+ get_alerts(ctx)"], "F05"),
    "b": cls("ShoppingListService", ["adds low / used-up items"], "F11"),
    "c": cls("HouseholdNotifier", ["offer and claim notifications"], "F15"),
    "d": cls("CostSplitService", ["records Shared purchases"], "F14"),
}, ["a -> obs [%s]" % IMPL, "b -> obs [%s]" % IMPL, "c -> obs [%s]" % IMPL, "d -> obs [%s]" % IMPL,
    'inv -> obs [arrowhead=open, arrowtail=odiamond, dir=both, xlabel=" 0..*"]'], same_rank=[("inv", "obs")])

# ---- Strategy ----
write("pattern-strategy", "Strategy: AI first, rules as fallback; fridge or typed ingredients", {
    "ps": cls("PlacementService", ["+ suggest(name): (Location, reason, source)"], "Context (F02)"),
    "pst": cls("PlacementStrategy", ["+ choose_location(name)"], "Strategy", True, IFACE),
    "lps": cls("LLMPlacementStrategy"), "rps": cls("RuleBasedPlacementStrategy"),
    "es": cls("ExpiryService", ["+ estimate(name, location, added_on)"], "Context (F04)"),
    "est": cls("ExpiryEstimator", ["+ estimate_days(name, location)"], "Strategy", True, IFACE),
    "lee": cls("LLMExpiryEstimator"), "ree": cls("RuleBasedExpiryEstimator"),
    "ra": cls("RecipeAgent", ["+ suggest(ctx, request, source)"], "Context (F07/F10)"),
    "isrc": cls("IngredientSource", ["+ get_items(ctx)"], "Strategy", True, IFACE),
    "fis": cls("FridgeIngredientSource", ["F07"]), "mis": cls("ManualIngredientSource", ["F10"]),
}, ["lps -> pst [%s]" % IMPL, "rps -> pst [%s]" % IMPL, 'ps -> pst [arrowhead=open, xlabel=" primary, fallback"]',
    "lee -> est [%s]" % IMPL, "ree -> est [%s]" % IMPL, 'es -> est [arrowhead=open, xlabel=" primary, fallback"]',
    "fis -> isrc [%s]" % IMPL, "mis -> isrc [%s]" % IMPL, 'ra -> isrc [arrowhead=open]'],
    rankdir="LR")

# ---- Command ----
write("pattern-command", "Command: undoable inventory changes", {
    "fac": cls("FridgemateFacade", ["+ add_item / update_item / remove_item", "+ cook / offer_item / claim_item",
                                    "+ confirm_changes / undo"], "Client"),
    "hist": cls("CommandHistory", ["- history: dict[member_id, list]", "+ run(ctx, command)", "+ undo_last(ctx): bool"],
                "Invoker"),
    "cmd": cls("InventoryCommand", ["+ execute()", "+ undo()", "+ undoable(): bool"], "Command", True, IFACE),
    "a": cls("AddItemCommand"), "b": cls("UpdateItemCommand"), "c": cls("RemoveItemCommand"),
    "d": cls("OfferItemCommand", ["undo = withdraw offer"]), "e": cls("ClaimItemCommand", ["undoable() = False"]),
    "f": cls("CookRecipeCommand", ["deducts every ingredient,", "adds leftovers; one undo"]),
    "inv": cls("InventoryService", [], "Receiver", fill=PAT),
}, [f"{x} -> cmd [{IMPL}]" for x in "abcdef"] +
   ['hist -> cmd [arrowhead=open, arrowtail=odiamond, dir=both, xlabel=" 0..*"]', f"fac -> hist [{DEP}, xlabel=\" run\"]",
    f"a -> inv [{DEP}]", f"f -> inv [{DEP}]", f"c -> inv [{DEP}]"],
    rankdir="LR")

# ---- Adapter + Factory Method ----
write("pattern-adapter-factory", "Adapter and Factory Method: outside services behind one interface", {
    "fac": cls("LLMClientFactory", ["+ create_client(): LLMClient"], "Factory Method", fill=PAT),
    "llm": cls("LLMClient", ["+ generate(system, messages,", "    json_mode, images): LLMResponse"], "Target", True, IFACE),
    "gem": cls("GeminiClient", ["- models: list (quota fallback)", "- thinking_level", "+ generate(...)"], "Adapter"),
    "oll": cls("OllamaClient", ["+ generate(...)"], "Adapter"),
    "gapi": cls("Gemini REST API", [], "Adaptee"), "oapi": cls("Ollama /api/chat", [], "Adaptee"),
    "rs": cls("RecipeSource", ["+ search_by_ingredient(name, cuisine)", "+ get_recipe(id): Recipe"], "Target", True, IFACE),
    "mdb": cls("MealDBRecipeSource", ["+ search_by_ingredient(...)", "+ get_recipe(...)"], "Adapter"),
    "mapi": cls("TheMealDB JSON API", [], "Adaptee"),
    "agents": cls("Agents and LLM strategies", [], "Client"),
}, [f"gem -> llm [{IMPL}]", f"oll -> llm [{IMPL}]", f"mdb -> rs [{IMPL}]",
    f"gem -> gapi [{DEP}]", f"oll -> oapi [{DEP}]", f"mdb -> mapi [{DEP}]",
    f'fac -> gem [{DEP}, xlabel=" creates"]', f'fac -> oll [{DEP}, xlabel=" creates"]',
    "agents -> llm [arrowhead=open]", "agents -> rs [arrowhead=open]"], rankdir="TB",
    same_rank=[("gem", "oll", "mdb")])

# ---- Agents and tools ----
write("class-3-agents-tools", "Agents and tools", {
    "base": cls("BaseAgent", ["+ run_tool_loop(ctx, system, messages,", "    registry, trace, max_steps=6): LoopResult",
                              "ask_json(...): schema check + 1 retry (G5)"], abstract=True),
    "ra": cls("RecipeAgent", ["+ suggest(ctx, request, source)", "+ build_suggestions(...)"], "F07 F08 F10"),
    "mpa": cls("MealPlanAgent", ["+ plan(ctx, days, meals, minutes)", "+ outdated_meals / replan"], "F13"),
    "fca": cls("FridgeCommandAgent", ["+ handle(ctx, message): CommandReply", "+ take_pending(ctx, id)"], "F12"),
    "rp": cls("ReceiptParser", ["+ parse_image(bytes, mime)", "+ parse_text(text)"], "F03"),
    "mem": cls("ConversationMemory", ["+ history(member_id)", "+ remember(...)"]),
    "trace": cls("AgentTrace", ["+ add(kind, detail, tool, args)"], "G8"),
    "reg": cls("ToolRegistry", ["+ describe()", "+ run(name, ctx, args)"]),
    "tool": cls("Tool", ["+ run(ctx, args)"], abstract=True, fill=IFACE),
    "t1": cls("GetInventoryTool\nGetExpiringItemsTool\nSearchRecipesTool"),
    "t2": cls("ConvertUnitsTool\nValidateRecipeTool (G3)\nProposeInventoryChangeTool (G4)"),
    "llm": cls("LLMClient", [], "interface", True, IFACE),
}, [f"ra -> base [{REAL}]", f"mpa -> base [{REAL}]", f"fca -> base [{REAL}]",
    "mpa -> ra [arrowhead=open, xlabel=\" reuses tools\"]", "fca -> mem [arrowhead=open]",
    f"base -> trace [{DEP}]", f"base -> reg [{DEP}]", "reg -> tool [arrowhead=open, arrowtail=odiamond, dir=both]",
    f"t1 -> tool [{IMPL}]", f"t2 -> tool [{IMPL}]", "base -> llm [arrowhead=open]", "rp -> llm [arrowhead=open]"],
    rankdir="TB")
print("ok")
