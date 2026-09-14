import json
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from odarka import shopping_agent as agent
from odarka.web import app


def plan(budget=500):
    return agent.Plan(items=[agent.Item(kind="potato", quantity=2.0, unit="kg"),
        agent.Item(kind="chicken", quantity=1.0, unit="kg"),
        agent.Item(kind="eggs", quantity=10.0, unit="pcs")],
        budget=float(budget), needs_clarification=False)


def product(**extra):
    return {"name": "Картопля мита", "slug": "kartoplia-1", "price": 20.0,
            "weighted": True, "step": 0.1, "stock": 100.0, "available": True,
            "displayRatio": "100г", **extra}


def goods():
    return {"potato": [product()], "chicken": [product(name="Філе куряче", price=200.0)],
            "eggs": [product(name="Яйця курячі", price=70.0, weighted=False, step=1.0, displayRatio="10шт")]}


def test_budget_uses_actual_price_per_kg_and_exact_package_count():
    result = agent.calculate(plan(), goods())
    assert result["total"] == 310.0 and result["remaining"] == 190.0
    assert result["decision"] == "within_budget"
    assert result["rows"][2]["selected"]["purchase_units"] == 1.0
    assert agent.calculate(plan(300), goods())["decision"] == "over_budget"


@pytest.mark.parametrize("changes", [{"price": True}, {"price": float("nan")}, {"step": 0.0},
    {"stock": 1.0}, {"available": False}, {"weighted": "true"}, {"slug": "<script>"},
    {"name": "Батат"}, {"name": "Картопля фрі заморожена"}, {"weighted": False, "displayRatio": "1,5кг"}])
def test_uncertain_or_incompatible_rows_cannot_be_selected(changes):
    assert agent.candidate(product(**changes), plan().items[0]) is None


def test_unknown_units_and_excess_packages_are_not_silent_substitutions():
    eggs = plan().items[2]
    assert agent.candidate(product(weighted=False, displayRatio="6шт", step=1.0), eggs) is None
    assert agent.candidate(product(weighted=False, displayRatio="10", step=1.0), eggs) is None
    assert agent.candidate(product(weighted=False, displayRatio="0шт", step=1.0), eggs) is None
    assert agent.candidate(product(weighted=False, displayRatio="1000г", step=1.0), plan().items[0])["cost"] == 40.0


def test_no_all_store_cheapest_or_complete_claim_for_partial_data():
    data = goods()
    data["eggs"] = []
    result = agent.calculate(plan(), data)
    assert result["decision"] == "incomplete" and result["missing"] == ["Курячі яйця"]
    assert "fetched" in result["selection_scope"]


def test_image_boundary_drops_untrusted_urls():
    for url in ["http://images.silpo.ua/a.jpg", "https://evil.example/a.jpg", "https://x:secret@images.silpo.ua/a.jpg"]:
        assert agent.candidate(product(image=url), plan().items[0])["image"] is None


def test_plan_validation_has_no_authority_fields_or_duplicate_items():
    raw = plan().model_dump()
    for change in [{"budget": True}, {"budget": float("inf")}, {"authorize_purchase": True},
                   {"items": [raw["items"][0], raw["items"][0]]}]:
        with pytest.raises(ValidationError):
            agent.Plan.model_validate({**raw, **change})
    with pytest.raises(ValidationError):
        agent.Item(kind="eggs", quantity=1.5, unit="pcs")


def test_real_model_adapter_requires_completed_valid_output():
    reply = {"model": agent.MODEL, "done": True, "done_reason": "stop",
             "message": {"content": plan().model_dump_json(), "thinking": "PRIVATE"}}
    response = Mock()
    response.json.return_value = reply
    with patch.object(agent.requests, "post", return_value=response) as post:
        parsed, receipt = agent.interpret(agent.DEFAULT_REQUEST)
    assert parsed == plan() and receipt["response_validated"]
    assert "PRIVATE" not in json.dumps(receipt)
    assert post.call_args.kwargs["json"]["think"] is False
    reply["done_reason"] = "length"
    with patch.object(agent.requests, "post", return_value=response), pytest.raises(ValueError):
        agent.interpret(agent.DEFAULT_REQUEST)


def test_model_failure_or_clarification_never_invokes_mcp():
    with patch.object(agent, "interpret", side_effect=RuntimeError("SECRET")), patch.object(agent, "SilpoMCP") as mcp:
        result = agent.run_demo(agent.DemoRequest())
    assert not result["ok"] and result["stage"] == "model" and "SECRET" not in json.dumps(result)
    mcp.assert_not_called()
    draft = plan()
    draft.needs_clarification = True
    with patch.object(agent, "interpret", return_value=(draft, {})), patch.object(agent, "SilpoMCP") as mcp:
        assert agent.run_demo(agent.DemoRequest())["stage"] == "clarification"
    mcp.assert_not_called()


class FakeMCP:
    calls = []
    changed_schema = False

    def __init__(self, *args): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def list_tools(self):
        return [{"name": name, "inputSchema": {"type": "object", "required": ["unavailable"] if self.changed_schema else []},
                 "annotations": {"readOnlyHint": True}} for name in agent.READ_TOOLS]

    def call(self, name, args):
        from datetime import timedelta
        now = agent.datetime.now(agent.timezone.utc)
        self.calls.append((name, args))
        if name == "silpo_list_branches":
            data = {"branches": [{"branchId": "b1", "city": "Київ", "address": "Public street", "private": "SECRET"}]}
        elif name == "silpo_get_categories":
            data = {"categories": [{"title": title, "slug": key} for key, title in agent.CATEGORIES.items()]}
        elif name == "silpo_get_time_slots":
            data = {"slots": [{"start": (now + timedelta(hours=1)).isoformat(), "end": (now + timedelta(hours=2)).isoformat(), "deliveryType": "SelfPickup", "available": True}]}
        else:
            data = {"products": goods()[args["category"]]}
        return {"structuredContent": {"success": True, **data}}


def test_workflow_uses_real_contract_but_fixture_is_not_live_proof(tmp_path):
    FakeMCP.calls.clear()
    with patch.object(agent, "interpret", return_value=(plan(), {"verified": True})), patch.object(agent, "SilpoMCP", FakeMCP), patch.object(agent.config, "TRACE_DIR", tmp_path):
        draft = agent.run_demo(agent.DemoRequest(text=agent.DEFAULT_REQUEST + " PRIVATE_MARKER"))
        assert draft["phase"] == "needs_confirmation" and not FakeMCP.calls
        result = agent.run_demo(agent.DemoRequest(draft_id=draft["draft_id"], confirmed_plan=plan(), text=agent.DEFAULT_REQUEST + " PRIVATE_MARKER"))
    assert result["ok"] and result["read_only"] and not result["cart_changed"]
    assert len(FakeMCP.calls) == 6 and result["result"]["total"] == 310.0
    assert all(name in agent.READ_TOOLS for name, _ in FakeMCP.calls)
    assert "SECRET" not in json.dumps(result)
    assert "PRIVATE_MARKER" not in json.dumps(result)
    assert "PRIVATE_MARKER" not in next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_schema_drift_rejected_before_call(tmp_path):
    FakeMCP.calls.clear()
    with patch.object(agent, "interpret", return_value=(plan(), {})), patch.object(agent, "SilpoMCP", FakeMCP), patch.object(FakeMCP, "changed_schema", True), patch.object(agent.config, "TRACE_DIR", tmp_path):
        draft = agent.run_demo(agent.DemoRequest())
        assert not agent.run_demo(agent.DemoRequest(draft_id=draft["draft_id"], confirmed_plan=plan()))["ok"]
    assert not FakeMCP.calls


def test_model_budget_change_cannot_become_a_confirmed_proposal():
    with patch.object(agent, "interpret", return_value=(plan(500), {})), patch.object(agent, "SilpoMCP") as mcp:
        draft = agent.run_demo(agent.DemoRequest(text="Картопля 2 кг, куряче філе 1 кг, яйця 10 шт. Бюджет 300 грн."))
        assert draft["phase"] == "needs_confirmation" and "result" not in draft
        result = agent.run_demo(agent.DemoRequest(draft_id=draft["draft_id"], confirmed_plan=plan(300)))
        assert not result["ok"] and result["stage"] == "confirmation"
    mcp.assert_not_called()


def test_expired_unknown_and_consumed_confirmation_rejected():
    with patch.object(agent, "interpret", return_value=(plan(), {})), patch.object(agent, "SilpoMCP") as mcp:
        draft = agent.run_demo(agent.DemoRequest())
        key = draft["draft_id"]
        agent.DRAFTS[key] = (0, plan(), {})
        assert not agent.run_demo(agent.DemoRequest(draft_id=key, confirmed_plan=plan()))["ok"]
        assert not agent.run_demo(agent.DemoRequest(draft_id="0" * 32, confirmed_plan=plan()))["ok"]
    mcp.assert_not_called()


def test_raw_chicken_does_not_accept_smoked_or_marinated_meat():
    for name in ["Філе куряче копчене", "Філе куряче мариноване", "Філе куряче запечене"]:
        assert agent.candidate(product(name=name), plan().items[1]) is None
    assert agent.candidate(product(name="Картопля тушкована"), plan().items[0]) is None


def test_api_origin_size_and_failure_boundaries():
    with TestClient(app) as client, patch.object(agent, "run_demo", return_value={"ok": False, "stage": "model"}) as run:
        assert client.post("/api/agent-demo", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/agent-demo", json={"text": "x" * 5000}).status_code == 400
        assert client.post("/api/agent-demo", json={"text": "short"}).status_code == 400
        assert not run.called
        assert client.post("/api/agent-demo", json={}).json()["stage"] == "model"
