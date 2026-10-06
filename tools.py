"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.
"""

import os
import re
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # lets non-LLM tests run before dependencies are installed
    def load_dotenv():
        return False

from utils.data_loader import load_listings

load_dotenv()

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


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
    return Groq(api_key=api_key)


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
        tokens = re.findall(r"xxs|xxl|xs|xl|s|m|l", listing_size)
        return requested in tokens

    # Numeric shoe/waist size: 8 should match "US 8" but not "US 8.5".
    if re.fullmatch(r"\d+(?:\.\d+)?", requested):
        return bool(
            re.search(
                rf"(?<![\d.]){re.escape(requested)}(?![\d.])",
                listing_size,
            )
        )

    return requested in listing_size


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
        price = float(listing.get("price", 0))
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
    except Exception as exc:
        return f"I couldn't generate an outfit suggestion right now: {exc}"


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
    except Exception as exc:
        return f"I couldn't create the fit card right now: {exc}"
