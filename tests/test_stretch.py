import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock

import pytest
import agent
import tools
from profiles import ProfileStore, validate_profile
from utils.data_loader import get_empty_wardrobe


@pytest.fixture
def item():
    return tools.load_listings()[5]


@pytest.fixture
def llm(monkeypatch):
    fake = Mock(return_value="A complete outfit with jeans and boots.")
    monkeypatch.setattr(tools, "_call_llm", fake)
    return fake


def test_size_is_not_substring():
    assert not tools._size_matches("S", "One Size / Oversized")
    assert not tools._size_matches("M", "Medium")
    assert tools._size_matches("M", "S/M")
    assert not tools._size_matches("8", "US 8.5")
    assert tools._size_matches("8", "US 8")


def test_retry_drops_size_only(monkeypatch, llm, item):
    search = Mock(side_effect=[[], [item]])
    monkeypatch.setattr(agent, "search_listings", search)
    session = agent.run_agent("graphic tee size XXS under $30", get_empty_wardrobe())
    assert session["error"] is None
    assert search.call_args_list[0].kwargs == {"size": "XXS", "max_price": 30.0}
    assert search.call_args_list[1].kwargs == {"size": None, "max_price": 30.0}
    assert search.call_args_list[0].args == search.call_args_list[1].args
    assert len(session["search_attempts"]) == 2
    assert any("budget is unchanged" in notice for notice in session["notices"])
    assert any("Selected listing size: L" in notice for notice in session["notices"])


def test_retry_is_bounded_and_stops(monkeypatch):
    search = Mock(return_value=[])
    outfit = Mock()
    monkeypatch.setattr(agent, "search_listings", search)
    monkeypatch.setattr(agent, "suggest_outfit", outfit)
    session = agent.run_agent("ballgown size XXS under $5", get_empty_wardrobe())
    assert search.call_count == 2
    outfit.assert_not_called()
    assert session["fit_card"] is None
    assert "Try a broader description" in session["error"]


def test_no_size_no_retry(monkeypatch):
    search = Mock(return_value=[])
    monkeypatch.setattr(agent, "search_listings", search)
    agent.run_agent("ballgown under $5", get_empty_wardrobe())
    assert search.call_count == 1


def test_price_comparison_excludes_self_and_uses_median(monkeypatch):
    selected = {"id": "a", "price": 20, "category": "tops", "style_tags": ["vintage"]}
    peers = [selected, {**selected, "id": "b", "price": 10},
             {**selected, "id": "c", "price": 30},
             {**selected, "id": "d", "price": 100, "category": "shoes"}]
    monkeypatch.setattr(tools, "load_listings", lambda: peers)
    result = tools.compare_prices(selected)
    assert result["comparable_ids"] == ["b", "c"]
    assert result["median_price"] == 20
    assert result["difference_pct"] == 0
    assert result["verdict"] == "fair"


@pytest.mark.parametrize("price,verdict", [(10, "below typical"), (30, "above typical")])
def test_price_verdict_thresholds(monkeypatch, price, verdict):
    item = {"id": "a", "price": price, "category": "tops", "style_tags": ["vintage"]}
    monkeypatch.setattr(tools, "load_listings", lambda: [
        {**item, "id": "b", "price": 20}, {**item, "id": "c", "price": 20}])
    assert tools.compare_prices(item)["verdict"] == verdict


def test_price_insufficient_and_dataset_failure(monkeypatch, item):
    monkeypatch.setattr(tools, "load_listings", lambda: [item])
    assert tools.compare_prices(item)["status"] == "insufficient_data"
    monkeypatch.setattr(tools, "load_listings", Mock(side_effect=OSError("injected read failure")))
    assert tools.compare_prices(item)["status"] == "unavailable"
    assert tools.search_listings("tee") == []


def test_profile_survives_new_store_and_delete(tmp_path):
    profile = {"wardrobe": {"items": [{"name": "My boots", "colors": ["black"]}]},
               "style_preferences": "grunge", "size": "M", "max_price": 35}
    store = ProfileStore(tmp_path)
    saved = store.save("../../my-profile", profile)
    assert ProfileStore(tmp_path).load("../../my-profile") == saved
    assert ProfileStore(tmp_path).load("someone else") is None
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert "My boots" in next(tmp_path.glob("*.json")).read_text()
    store.delete("../../my-profile")
    assert store.load("../../my-profile") is None


@pytest.mark.parametrize("update", [{"max_price": -1}, {"max_price": float("nan")},
                                    {"wardrobe": {"items": ["bad"]}},
                                    {"wardrobe": {"items": [{"name": "x", "colors": "red"}]}}])
def test_invalid_profile_is_rejected(update):
    with pytest.raises((ValueError, TypeError)):
        validate_profile({"wardrobe": {"items": []}, **update})


def test_profile_query_overrides_and_preferences(monkeypatch, llm, item):
    search = Mock(return_value=[item])
    monkeypatch.setattr(agent, "search_listings", search)
    profile = {"wardrobe": {"items": []}, "style_preferences": "earth tones",
               "size": "L", "max_price": 40}
    first = agent.run_agent("graphic tee", get_empty_wardrobe(), profile=profile)
    assert first["parsed"]["size"] == "L"
    assert first["parsed"]["max_price"] == 40
    assert "earth tones" in llm.call_args_list[0].args[0]
    second = agent.run_agent("graphic tee size M under $20", get_empty_wardrobe(), profile=profile)
    assert second["parsed"]["size"] == "M"
    assert second["parsed"]["max_price"] == 20


def feed_item(title, days=0, url="https://www.whowhatwear.com/fashion/example"):
    date = format_datetime(datetime.now(timezone.utc) - timedelta(days=days))
    return f"<item><title>{title}</title><link>{url}</link><pubDate>{date}</pubDate></item>"


def feed(*entries):
    return ("<rss><channel>" + "".join(entries) + "</channel></rss>").encode()


def test_trends_are_recent_sourced_size_filtered_and_deduplicated(monkeypatch):
    monkeypatch.setattr(tools, "_fetch_trend_feed", lambda: feed(
        feed_item("Vintage denim", 1), feed_item("Vintage denim", 1),
        feed_item("Vintage grunge", 40, "https://www.whowhatwear.com/old")))
    monkeypatch.setattr(tools, "load_listings", lambda: [
        {"id": "m", "size": "M", "style_tags": ["vintage"]},
        {"id": "l", "size": "L", "style_tags": ["vintage"]},
        {"id": "g", "size": "M", "style_tags": ["grunge"]}])
    result = tools.check_trends("M")
    assert result["status"] == "ok"
    assert len(result["trends"]) == 1
    assert result["trends"][0]["listing_ids"] == ["m"]
    assert result["trends"][0]["post_count"] == 1
    assert result["trends"][0]["sources"][0]["published_at"]


def test_trends_no_matching_size(monkeypatch):
    monkeypatch.setattr(tools, "_fetch_trend_feed", lambda: feed(feed_item("Vintage", 1)))
    assert tools.check_trends("XXS")["status"] == "empty"


@pytest.mark.parametrize("failure", [OSError("blocked"), ValueError("too large")])
def test_trend_network_failure(monkeypatch, failure):
    monkeypatch.setattr(tools, "_fetch_trend_feed", Mock(side_effect=failure))
    result = tools.check_trends()
    assert result["status"] == "unavailable"
    assert result["trends"] == []
    assert "Check your connection" in result["message"]


@pytest.mark.parametrize("data", [b"bad xml", b"<html>not RSS</html>"])
def test_trend_malformed_feed(monkeypatch, data):
    monkeypatch.setattr(tools, "_fetch_trend_feed", lambda: data)
    assert tools.check_trends()["status"] == "unavailable"


def test_advisory_failures_do_not_stop_outfit(monkeypatch, llm):
    monkeypatch.setattr(agent, "compare_prices", lambda item: {"status": "unavailable"})
    monkeypatch.setattr(agent, "check_trends", lambda size: {"status": "unavailable"})
    session = agent.run_agent("graphic tee under $30", get_empty_wardrobe(), include_trends=True)
    assert session["error"] is None
    assert session["fit_card"]
    assert "check_trends" in session["tool_calls"]


def test_actual_outfit_api_failure_stops_card(monkeypatch):
    monkeypatch.setattr(tools, "_call_llm", Mock(side_effect=RuntimeError("injected service outage")))
    card = Mock()
    monkeypatch.setattr(agent, "create_fit_card", card)
    session = agent.run_agent("graphic tee under $30", get_empty_wardrobe())
    card.assert_not_called()
    assert "Check GROQ_API_KEY" in session["error"]
    assert "injected" not in session["error"]
    assert session["selected_item"] is not None


def test_actual_card_api_failure_preserves_outfit(monkeypatch):
    monkeypatch.setattr(tools, "_call_llm", Mock(side_effect=["My outfit", RuntimeError("injected")]))
    session = agent.run_agent("graphic tee under $30", get_empty_wardrobe())
    assert session["outfit_suggestion"] == "My outfit"
    assert session["fit_card"] is None
    assert "outfit is still available" in session["error"]


def test_empty_llm_output_stops_card(monkeypatch):
    monkeypatch.setattr(tools, "_call_llm", lambda *a, **k: "")
    session = agent.run_agent("graphic tee under $30", get_empty_wardrobe())
    assert session["error"]
    assert "create_fit_card" not in session["tool_calls"]


def test_ui_retains_partial_results(monkeypatch):
    import app
    monkeypatch.setattr(tools, "_call_llm", Mock(side_effect=["My outfit", RuntimeError("injected")]))
    listing, outfit, card = app.handle_query("graphic tee under $30", "Example wardrobe")
    assert "Price" not in card
    assert "PRICE CHECK" in listing
    assert "couldn't create the fit card" in listing
    assert outfit == "My outfit"
    assert card == ""


def test_ui_profiles_load_then_use_in_query(monkeypatch, tmp_path, llm):
    import app
    monkeypatch.setattr(app, "STORE", ProfileStore(tmp_path))
    wardrobe = json.dumps({"items": [{"name": "My sneakers"}]})
    assert "saved locally" in app.save_profile("demo", wardrobe, "grunge", "L", 30)
    loaded = app.load_profile("demo")
    assert loaded[4] == "Custom / saved wardrobe"
    listing, outfit, card = app.handle_query("graphic tee", loaded[4], *loaded[:4])
    assert card
    assert "My sneakers" in llm.call_args_list[0].args[0]
    assert "grunge" in llm.call_args_list[0].args[0]
    assert "deleted" in app.delete_profile("demo")


def test_gradio_interface_builds():
    import app
    demo = app.build_interface()
    assert demo.config["components"]


def test_gradio_blank_optional_fields_are_none(llm, monkeypatch, tmp_path):
    import app
    listing, outfit, card = app.handle_query('graphic tee under $30', 'Example wardrobe',
                                             None, None, None, None, False)
    assert 'Tool trace:' in listing
    assert outfit and card
    monkeypatch.setattr(app, 'STORE', ProfileStore(tmp_path))
    assert 'saved locally' in app.save_profile('blank-optionals', '{"items": []}', None, None, None)
