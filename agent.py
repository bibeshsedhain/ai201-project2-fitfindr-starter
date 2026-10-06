"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize a fresh state object for one FitFindr interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


def _parse_query(query: str) -> dict:
    """Extract description, optional size, and optional maximum price."""
    text = " ".join(query.strip().split())

    price_match = re.search(
        r"(?:under|below|less\s+than|max(?:imum)?|up\s+to)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
        text,
        flags=re.IGNORECASE,
    )
    if not price_match:
        price_match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)\s*(?:or\s+less|max)?", text, re.IGNORECASE)
    max_price = float(price_match.group(1)) if price_match else None

    size_match = re.search(
        r"(?:\bin\s+)?\bsize\s+(xxs|xs|s|m|l|xl|xxl|\d+(?:\.\d+)?)\b",
        text,
        flags=re.IGNORECASE,
    )
    size = size_match.group(1).upper() if size_match else None

    description = text
    if price_match:
        description = description.replace(price_match.group(0), " ")
    if size_match:
        description = description.replace(size_match.group(0), " ")

    description = re.sub(
        r"\b(?:i(?:'m| am)?\s+)?(?:looking for|searching for|want|find me|find)\b",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"[,;]+", " ", description)
    description = " ".join(description.split()).strip(" .")

    return {
        "description": description or text,
        "size": size,
        "max_price": max_price,
    }


def _tool_returned_error(value: str) -> bool:
    """Identify descriptive error strings returned by an LLM-backed tool."""
    lowered = value.lower().strip()
    return lowered.startswith("i need ") or lowered.startswith("i couldn't ")


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the conditional FitFindr planning loop and return the completed session.
    """
    session = _new_session(query, wardrobe)

    if not isinstance(query, str) or not query.strip():
        session["error"] = "Please describe the secondhand item you're looking for."
        return session

    # Step 1: parse the user's natural-language constraints.
    session["parsed"] = _parse_query(query)

    # Step 2: search. The next step depends on whether this succeeds.
    parsed = session["parsed"]
    results = search_listings(
        parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        constraints = []
        if parsed["size"]:
            constraints.append(f"size {parsed['size']}")
        if parsed["max_price"] is not None:
            constraints.append(f"under ${parsed['max_price']:g}")
        constraint_text = f" ({', '.join(constraints)})" if constraints else ""
        session["error"] = (
            f"I couldn't find listings matching \"{parsed['description']}\"{constraint_text}. "
            "Try a broader description, a different size, or a higher price limit."
        )
        return session

    # Step 3: put the selected search result into shared state.
    session["selected_item"] = results[0]

    # Step 4: use that same state value for styling.
    outfit = suggest_outfit(session["selected_item"], session["wardrobe"])
    session["outfit_suggestion"] = outfit
    if not outfit or _tool_returned_error(outfit):
        session["error"] = outfit or "I couldn't create an outfit suggestion."
        return session

    # Step 5: use both prior tool outputs to create the final artifact.
    fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    session["fit_card"] = fit_card
    if not fit_card or _tool_returned_error(fit_card):
        session["error"] = fit_card or "I couldn't create the fit card."

    return session


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
