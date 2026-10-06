import agent
import tools
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


def test_search_returns_results():
    results = tools.search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "tee" in results[0]["title"].lower() or "tee" in " ".join(results[0]["style_tags"]).lower()


def test_search_empty_results():
    results = tools.search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = tools.search_listings("jacket", size=None, max_price=50)
    assert results
    assert all(item["price"] <= 50 for item in results)


def test_search_size_filter():
    results = tools.search_listings("track jacket", size="M", max_price=None)
    assert results
    assert results[0]["id"] == "lst_004"


def test_suggest_outfit_empty_wardrobe(monkeypatch):
    monkeypatch.setattr(
        tools,
        "_call_llm",
        lambda prompt, temperature=0.7: "Pair it with relaxed denim and simple sneakers for an easy vintage look.",
    )
    item = tools.search_listings("graphic tee", max_price=30)[0]
    result = tools.suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip()


def test_suggest_outfit_uses_wardrobe(monkeypatch):
    seen = {}

    def fake_llm(prompt, temperature=0.7):
        seen["prompt"] = prompt
        return "Wear it with your Baggy straight-leg jeans, dark wash and Chunky white sneakers."

    monkeypatch.setattr(tools, "_call_llm", fake_llm)
    item = tools.search_listings("graphic tee", max_price=30)[0]
    result = tools.suggest_outfit(item, get_example_wardrobe())
    assert "Baggy straight-leg jeans" in seen["prompt"]
    assert result


def test_create_fit_card_empty_outfit():
    item = tools.search_listings("graphic tee", max_price=30)[0]
    result = tools.create_fit_card("", item)
    assert "need a complete outfit" in result.lower()


def test_create_fit_card_success(monkeypatch):
    monkeypatch.setattr(
        tools,
        "_call_llm",
        lambda prompt, temperature=0.7: "Thrifted this faded graphic tee for $19 on depop. Easy grunge layers all day.",
    )
    item = tools.search_listings("graphic tee", max_price=30)[0]
    result = tools.create_fit_card("Wear it with baggy jeans and chunky sneakers.", item)
    assert result


def test_parse_query():
    parsed = agent._parse_query("I'm looking for a 90s track jacket in size M under $50")
    assert parsed["description"] == "a 90s track jacket"
    assert parsed["size"] == "M"
    assert parsed["max_price"] == 50.0


def test_agent_stops_after_empty_search(monkeypatch):
    called = {"outfit": False}

    monkeypatch.setattr(agent, "search_listings", lambda *args, **kwargs: [])

    def should_not_run(*args, **kwargs):
        called["outfit"] = True
        raise AssertionError("suggest_outfit should not run after an empty search")

    monkeypatch.setattr(agent, "suggest_outfit", should_not_run)
    session = agent.run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    assert session["error"] is not None
    assert session["fit_card"] is None
    assert called["outfit"] is False


def test_agent_happy_path_state_flow(monkeypatch):
    item = {
        "id": "x",
        "title": "Test Tee",
        "description": "test",
        "category": "tops",
        "style_tags": ["vintage"],
        "size": "M",
        "condition": "good",
        "price": 20.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    seen = {}

    monkeypatch.setattr(agent, "search_listings", lambda *args, **kwargs: [item])

    def fake_outfit(new_item, wardrobe):
        seen["outfit_item"] = new_item
        return "Test outfit"

    def fake_card(outfit, new_item):
        seen["card_outfit"] = outfit
        seen["card_item"] = new_item
        return "Test fit card"

    monkeypatch.setattr(agent, "suggest_outfit", fake_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_card)

    session = agent.run_agent("vintage tee size M under $30", get_example_wardrobe())
    assert session["selected_item"] is item
    assert seen["outfit_item"] is item
    assert seen["card_item"] is item
    assert seen["card_outfit"] == session["outfit_suggestion"]
    assert session["fit_card"] == "Test fit card"
    assert session["error"] is None
