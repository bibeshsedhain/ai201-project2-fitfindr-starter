"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.
"""

import os
import math
import statistics
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import urllib.request
import xml.etree.ElementTree as ET
import re
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # lets non-LLM tests run before dependencies are installed
    def load_dotenv():
        return False

from utils.data_loader import load_listings

load_dotenv()

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")


def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError(
            "The groq package is not installed. Run: pip install -r requirements.txt"
        ) from exc
    return Groq(api_key=api_key, timeout=20.0, max_retries=1)


def _call_llm(prompt: str, temperature: float = 0.7) -> str:
    """Send one prompt to Groq and return the model text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=500,
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def _tokenize(text: str) -> set[str]:
    """Convert text into meaningful lowercase search tokens."""
    stop_words = {
        "a", "an", "and", "the", "for", "with", "of", "to", "in", "on",
        "i", "im", "i'm", "looking", "find", "want", "please", "something",
        "piece", "pieces", "item", "items", "me", "my",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in stop_words and len(token) > 1
    }


def _size_matches(requested: str, listing_size: str) -> bool:
    """Return True when a requested size appears as a complete size token."""
    requested = requested.strip().lower()
    listing_size = listing_size.strip().lower()

    # Exact match is always accepted.
    if requested == listing_size:
        return True

    # Letter sizes: M should match S/M or M/L, but not words containing m.
    if requested in {"xxs", "xs", "s", "m", "l", "xl", "xxl"}:
        tokens = re.findall(r"(?<![a-z])(xxs|xxl|xs|xl|s|m|l)(?![a-z])", listing_size)
        return requested in tokens

    # Numeric shoe/waist size: 8 should match "US 8" but not "US 8.5".
    if re.fullmatch(r"\d+(?:\.\d+)?", requested):
        return bool(
            re.search(
                rf"(?<![\d.]){re.escape(requested)}(?![\d.])",
                listing_size,
            )
        )

    return requested == listing_size


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Returns matching listing dictionaries sorted by relevance. If nothing
    matches (or the dataset cannot be loaded), returns an empty list.
    """
    if not isinstance(description, str) or not description.strip():
        return []

    try:
        listings = load_listings()
    except (OSError, ValueError, TypeError):
        return []

    query_tokens = _tokenize(description)
    if not query_tokens:
        return []

    scored: list[tuple[int, float, dict[str, Any]]] = []

    for listing in listings:
        if not isinstance(listing, dict):
            continue
        try:
            price = float(listing["price"])
            if not math.isfinite(price) or price < 0:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        if max_price is not None and price > max_price:
            continue

        if size and not _size_matches(size, str(listing.get("size", ""))):
            continue

        title_tokens = _tokenize(str(listing.get("title", "")))
        description_tokens = _tokenize(str(listing.get("description", "")))
        category_tokens = _tokenize(str(listing.get("category", "")))
        tag_tokens = _tokenize(" ".join(listing.get("style_tags", [])))
        color_tokens = _tokenize(" ".join(listing.get("colors", [])))
        brand_tokens = _tokenize(str(listing.get("brand") or ""))

        # Title/category matches carry the most weight, followed by style tags.
        score = 0
        score += 4 * len(query_tokens & title_tokens)
        score += 3 * len(query_tokens & category_tokens)
        score += 2 * len(query_tokens & tag_tokens)
        score += 1 * len(query_tokens & description_tokens)
        score += 1 * len(query_tokens & color_tokens)
        score += 1 * len(query_tokens & brand_tokens)

        # Reward a direct phrase match in title/style data.
        normalized_query = " ".join(re.findall(r"[a-z0-9]+", description.lower()))
        searchable_phrase = " ".join(
            [
                str(listing.get("title", "")),
                str(listing.get("category", "")),
                " ".join(listing.get("style_tags", [])),
            ]
        ).lower()
        if normalized_query and normalized_query in re.sub(r"[^a-z0-9]+", " ", searchable_phrase):
            score += 6

        if score > 0:
            # Secondary ordering favors cheaper items when relevance ties.
            scored.append((score, price, listing))

    scored.sort(key=lambda row: (-row[0], row[1]))
    return [listing for _, _, listing in scored]


def _format_new_item(new_item: dict) -> str:
    return (
        f"Title: {new_item.get('title', 'Unknown item')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Size: {new_item.get('size', 'unknown')}\n"
        f"Price: ${new_item.get('price', 'unknown')}\n"
        f"Platform: {new_item.get('platform', 'unknown')}"
    )


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.
    If the wardrobe is empty, provide useful general styling advice instead.
    """
    if not isinstance(new_item, dict) or not new_item:
        return "I need a valid thrifted item before I can suggest an outfit."

    wardrobe_items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
    item_text = _format_new_item(new_item)
    preferences = wardrobe.get("style_preferences", "") if isinstance(wardrobe, dict) else ""
    item_text += f"\nUser style preferences: {preferences or 'not specified'}"

    if not wardrobe_items:
        prompt = f"""
You are FitFindr, a concise secondhand-fashion styling assistant.
The user is considering this item:

{item_text}

Their saved wardrobe is empty. Suggest 1-2 complete outfits using general types
of clothing they could pair with this item. Mention colors, silhouettes, shoes,
and the overall vibe. Do not pretend the user already owns any specific piece.
Keep the answer under 130 words and make it practical.
""".strip()
    else:
        wardrobe_lines = []
        for item in wardrobe_items:
            wardrobe_lines.append(
                f"- {item.get('name', 'Unnamed item')} "
                f"({item.get('category', 'unknown')}; "
                f"colors: {', '.join(item.get('colors', []))}; "
                f"style: {', '.join(item.get('style_tags', []))})"
            )

        prompt = f"""
You are FitFindr, a concise secondhand-fashion styling assistant.
The user is considering this thrifted item:

{item_text}

Their wardrobe contains:
{chr(10).join(wardrobe_lines)}

Suggest 1-2 complete outfits centered on the thrifted item. Use the exact names
of pieces from the wardrobe whenever possible. Include a top/bottom as needed,
shoes, an optional layer/accessory, and a specific style vibe. Do not invent
pieces and claim they are already in the wardrobe. Keep it under 150 words.
""".strip()

    try:
        response = _call_llm(prompt, temperature=0.75)
        if response:
            return response
        return "I couldn't generate an outfit suggestion. Please try again."
    except Exception:
        return "I couldn't generate an outfit suggestion. Check GROQ_API_KEY and GROQ_MODEL in .env, your connection, and Groq limits; then retry."


def create_fit_card(outfit: str, new_item: dict) -> str:
    """Generate a short, shareable outfit caption for the thrifted find."""
    if not isinstance(outfit, str) or not outfit.strip():
        return "I need a complete outfit suggestion before I can create a fit card."

    if not isinstance(new_item, dict) or not new_item:
        return "I need the selected thrifted item before I can create a fit card."

    item_text = _format_new_item(new_item)
    prompt = f"""
You are FitFindr. Write a casual, authentic social-media fit caption based on
this thrifted item and outfit idea.

THRIFTED ITEM:
{item_text}

OUTFIT IDEA:
{outfit.strip()}

Requirements:
- 2-4 short sentences.
- Naturally mention the item title/name, price, and platform exactly once each.
- Capture the outfit's specific vibe instead of sounding like a product listing.
- Sound like a real OOTD caption: relaxed, specific, and shareable.
- No hashtags unless they genuinely fit.
- Return only the caption.
""".strip()

    try:
        response = _call_llm(prompt, temperature=1.0)
        if response:
            return response
        return "I couldn't create the fit card. Please try again."
    except Exception:
        return "I couldn't create the fit card. Your outfit is still available. Check Groq credentials, model, connection and limits; then retry."


def compare_prices(new_item: dict) -> dict:
    """Estimate price fairness against other same-category, shared-tag listings."""
    base = {"status": "unavailable", "comparable_ids": [], "count": 0,
            "median_price": None, "difference_pct": None, "verdict": "unknown"}
    try:
        price = float(new_item["price"])
        if not math.isfinite(price) or price < 0:
            raise ValueError("Invalid price")
        tags = set(new_item.get("style_tags", []))
        peers = []
        for item in load_listings():
            if (item["id"] != new_item["id"]
                    and item["category"] == new_item["category"]
                    and tags.intersection(item.get("style_tags", []))):
                peer_price = float(item["price"])
                if math.isfinite(peer_price) and peer_price > 0:
                    peers.append(item)
        base.update(comparable_ids=[p["id"] for p in peers], count=len(peers))
        if len(peers) < 2:
            return {**base, "status": "insufficient_data", "message":
                    "Not enough comparable listings (need two). Compare seller condition and measurements manually."}
        median = statistics.median(float(p["price"]) for p in peers)
        difference = (price - median) / median * 100
        verdict = "below typical" if difference < -15 else "above typical" if difference > 15 else "fair"
        return {**base, "status": "ok", "median_price": round(median, 2),
                "difference_pct": round(difference, 1), "verdict": verdict,
                "message": f"{verdict.capitalize()}: ${price:.2f} versus ${median:.2f} median across {len(peers)} comparable mock listings. Condition, brand, shipping and measurements may differ."}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {**base, "message": "Price comparison unavailable. Check data/listings.json or compare seller prices manually."}


TREND_FEED_URL = "https://www.whowhatwear.com/feeds.xml"


def _fetch_trend_feed() -> bytes:
    request = urllib.request.Request(TREND_FEED_URL, headers={"User-Agent": "FitFindr/1.0 (student project)"})
    with urllib.request.urlopen(request, timeout=8) as response:
        data = response.read(8_000_001)
    if len(data) > 8_000_000:
        raise ValueError("Feed exceeded size limit")
    return data


def check_trends(size: str | None = None) -> dict:
    """Count recent public fashion-post style mentions and match size-filtered stock."""
    now = datetime.now(timezone.utc)
    base = {"status": "unavailable", "source": TREND_FEED_URL,
            "checked_at": now.isoformat(), "window_days": 30, "size": size,
            "posts_checked": 0, "trends": []}
    try:
        listings = load_listings()
        tags = sorted({tag.lower() for item in listings for tag in item.get("style_tags", [])})
        root = ET.fromstring(_fetch_trend_feed())
        if root.tag != "rss" or root.find("channel") is None:
            raise ValueError("Expected RSS feed")
        signals = {tag: [] for tag in tags}
        for post in root.findall("./channel/item"):
            try:
                published = parsedate_to_datetime(post.findtext("pubDate", ""))
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            if not now - timedelta(days=30) <= published <= now:
                continue
            link = post.findtext("link", "")
            if not link.startswith("https://"):
                continue
            base["posts_checked"] += 1
            title = post.findtext("title", "")
            text = " ".join([title, post.findtext("description", ""),
                             " ".join(c.text or "" for c in post.findall("category"))]).lower()
            text = re.sub(r"<[^>]*>", " ", text)
            for tag in tags:
                if re.search(r"(?<!\w)" + re.escape(tag) + r"(?!\w)", text):
                    if not any(source["url"] == link for source in signals[tag]):
                        signals[tag].append({"title": title, "url": link,
                                             "published_at": published.isoformat()})
        trends = []
        for tag, sources in signals.items():
            available = [item["id"] for item in listings if tag in
                         [t.lower() for t in item.get("style_tags", [])]
                         and (not size or _size_matches(size, str(item.get("size", ""))))]
            if sources and available:
                trends.append({"style": tag, "post_count": len(sources),
                               "listing_ids": available, "sources": sources[:3]})
        trends.sort(key=lambda trend: (-trend["post_count"], trend["style"]))
        return {**base, "status": "ok" if trends else "empty", "trends": trends[:5],
                "message": "Recent editorial mentions on Who What Wear, matched to mock inventory in your requested size. Counts reflect this feed sample, not global popularity or the authors' sizes."}
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError):
        return {**base, "message": "Live trend check unavailable. Check your connection and try again; your outfit search can continue."}
