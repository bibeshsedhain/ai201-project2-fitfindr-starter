# FitFindr 🛍️

FitFindr is a multi-tool AI thrift-shopping agent. A user describes a secondhand item they want, the agent searches the provided mock listings, chooses the most relevant result, suggests how to style it with their wardrobe, and creates a shareable outfit caption.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# source .venv/Scripts/activate    # Windows Git Bash
pip install -r requirements.txt
```

Create a `.env` file in the repository root:

```text
GROQ_API_KEY=your_key_here
```

Then run:

```bash
python -m pytest tests/
python app.py
```

The LLM-backed tools use Groq's `meta-llama/llama-4-scout-17b-16e-instruct` model.

---

## Tool Inventory

### `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

**Purpose:** Searches `data/listings.json` through the provided `load_listings()` helper. Optional price and size filters are applied before weighted keyword relevance scoring.

**Inputs:**
- `description` (`str`): item/style description, e.g. `"vintage graphic tee"`.
- `size` (`str | None`): optional size filter such as `"M"` or `"8"`.
- `max_price` (`float | None`): optional inclusive maximum price.

**Output:** A relevance-sorted `list[dict]`. Every listing dictionary contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`. It returns `[]` when no match exists.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

**Purpose:** Generates one or two complete outfits centered on the selected thrift listing. If the user has wardrobe items, their exact names are included in the prompt; if the wardrobe is empty, the tool gives general styling advice instead.

**Inputs:**
- `new_item` (`dict`): selected result from `search_listings`.
- `wardrobe` (`dict`): wardrobe object with an `items` list.

**Output:** A non-empty styling suggestion string or a descriptive error string if the item/API call is invalid.

### `create_fit_card(outfit: str, new_item: dict) -> str`

**Purpose:** Generates a 2–4 sentence social-media-style caption using the outfit suggestion and selected thrift item.

**Inputs:**
- `outfit` (`str`): result from `suggest_outfit`.
- `new_item` (`dict`): selected thrift listing.

**Output:** A shareable fit-card string. If `outfit` is empty, it returns a descriptive error message rather than raising an exception.

---

## How the Planning Loop Works

`run_agent()` creates one session dictionary, parses the user's natural-language query, and then decides which tool should run next based on the state of that session.

1. Parse `description`, optional `size`, and optional `max_price` from the query with regex.
2. Call `search_listings()` and save the list to `session["search_results"]`.
3. **Branch:** if the result list is empty, set `session["error"]` and return immediately. `suggest_outfit()` and `create_fit_card()` are not called.
4. If results exist, store the top result in `session["selected_item"]`.
5. Call `suggest_outfit()` with that exact dictionary plus `session["wardrobe"]`, and store its result in `session["outfit_suggestion"]`.
6. **Branch:** if the outfit tool reports an error, store it in `session["error"]` and return.
7. Call `create_fit_card()` with `session["outfit_suggestion"]` and the same `session["selected_item"]`.
8. Store the final string in `session["fit_card"]` and return the completed session.

This means the workflow is not a fixed unconditional sequence. Later calls happen only when the state produced by earlier calls is valid.

---

## State Management

The session dictionary is the single source of truth for one interaction:

```python
{
    "query": ...,
    "parsed": ...,
    "search_results": ...,
    "selected_item": ...,
    "wardrobe": ...,
    "outfit_suggestion": ...,
    "fit_card": ...,
    "error": ...,
}
```

The top search result is saved once in `selected_item` and passed directly into `suggest_outfit()`. The resulting outfit string is saved once in `outfit_suggestion` and then passed directly into `create_fit_card()` together with the same selected item. The user never needs to re-enter information between steps.

---

## Interaction Walkthrough

**User query:** `vintage graphic tee under $30`

**Step 1 — Tool called:**
- **Tool:** `search_listings`
- **Input:** `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- **Why this tool:** The agent needs a real listing before it can style anything.
- **Output:** A ranked list of matching listings under $30. The first dictionary is saved as `session["selected_item"]`.

**Step 2 — Tool called:**
- **Tool:** `suggest_outfit`
- **Input:** the exact selected listing dictionary plus the chosen wardrobe dictionary.
- **Why this tool:** Search succeeded, so the agent now has enough state to build a look around the item.
- **Output:** One or two complete outfit suggestions. This exact string is saved as `session["outfit_suggestion"]`.

**Step 3 — Tool called:**
- **Tool:** `create_fit_card`
- **Input:** `session["outfit_suggestion"]` and `session["selected_item"]`.
- **Why this tool:** A valid selected item and outfit suggestion both exist.
- **Output:** A casual 2–4 sentence fit caption mentioning the thrifted item, its price, platform, and vibe.

**Final output to user:**
The Gradio interface displays the selected listing in the first panel, the styling recommendation in the second panel, and the fit card in the third panel.

---

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match | Returns `[]`. The planning loop tells the user it could not find a match and suggests broadening the description, changing size, or raising the budget. The workflow stops before styling. |
| `suggest_outfit` | Wardrobe is empty | The tool still calls the LLM, but asks for general styling advice and does not claim the user owns specific pieces. |
| `suggest_outfit` | Item/API failure | Returns a readable error string. The planning loop stores the error and stops before fit-card generation. |
| `create_fit_card` | Outfit is empty | Returns `I need a complete outfit suggestion before I can create a fit card.` instead of raising an exception. |
| `create_fit_card` | API failure | Returns a readable error string so the app remains usable. |

### Concrete failure test

This query deliberately returns no results:

```text
designer ballgown size XXS under $5
```

The agent returns an actionable search message, leaves `selected_item`, `outfit_suggestion`, and `fit_card` empty, and never calls the outfit tool. The pytest suite includes a test that fails if `suggest_outfit()` is called on this branch.

---

## Testing

Run all tests from the repo root:

```bash
python -m pytest tests/
```

The suite covers:
- normal listing search,
- empty search results,
- price filtering,
- size filtering,
- empty-wardrobe outfit generation,
- wardrobe data flowing into the outfit prompt,
- missing outfit input for fit-card generation,
- query parsing,
- planning-loop early termination,
- selected-item and outfit state passing between tools.

---

## Spec Reflection

**One way `planning.md` helped during implementation:**
The spec made the state transitions explicit before wiring the tools together. In particular, defining the no-results branch first made it clear that an empty list is a valid search result that should terminate the workflow rather than being passed into `suggest_outfit`. It also kept the documented function interfaces synchronized with the starter signatures.

**One divergence from the spec, and why:**
The initial design treated query parsing as part of the planning loop without deciding exactly how it would work. During implementation I made it a small deterministic `_parse_query()` helper using regular expressions instead of another LLM call. This keeps the common `size M` and `under $30` extraction fast, testable, and free from unnecessary API usage while still leaving the three required agent tools unchanged.

---

## AI Usage

### Instance 1 — Implementing the required tools
I gave ChatGPT the starter `tools.py` function signatures/docstrings, the Tool Inventory requirements from the project description, and the mock-listing schema. I directed it to preserve the exact public signatures, use the provided `load_listings()` helper, implement deterministic filtering/scoring for search, and use Groq only for the two generative tools. I reviewed the implementation and added explicit size-token matching so `M` can match combined sizes such as `S/M` without matching unrelated text.

### Instance 2 — Implementing and verifying the planning loop
I gave ChatGPT the starter `agent.py`, the session dictionary fields, and the planning-loop/error-handling requirements. I directed it to make the flow conditional after every important result and to preserve tool outputs in the session. I then verified the result with pytest mocks: one test forces an empty search and asserts that `suggest_outfit()` is never called, while another verifies that the exact selected item and exact outfit string are passed into subsequent tools.

---

## Demo Video

**Video link:** _Add your 3–5 minute demo URL here before submitting._

The demo should show:
1. `vintage graphic tee under $30` with the example wardrobe.
2. Narration of `search_listings → selected_item → suggest_outfit → outfit_suggestion → create_fit_card`.
3. A no-results query such as `designer ballgown size XXS under $5` showing graceful early termination.
