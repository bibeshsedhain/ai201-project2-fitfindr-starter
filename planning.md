# FitFindr — planning.md

## Tools

### Tool 1: search_listings

**What it does:**
Searches the provided mock secondhand listings for items related to the user's description. It applies optional size and maximum-price filters first, then scores the remaining items by keyword overlap and returns the best matches first.

**Input parameters:**
- `description` (`str`): Natural-language description of the item the user wants, such as `"vintage graphic tee"`.
- `size` (`str | None`): Optional requested size. Matching is case-insensitive and allows combined sizes such as `S/M` to match `M`.
- `max_price` (`float | None`): Optional inclusive maximum price.

**What it returns:**
A `list[dict]` of matching listing dictionaries sorted by relevance. Each result contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`. If nothing matches, the function returns `[]`.

**What happens if it fails or returns nothing:**
The planning loop checks whether the returned list is empty. If it is empty, the agent stores a helpful message in `session["error"]`, recommends broadening the description, changing the size, or raising the price limit, and returns immediately. It does not call `suggest_outfit` with missing item data.

---

### Tool 2: suggest_outfit

**What it does:**
Uses the selected thrift listing and the user's wardrobe to generate one or two complete outfit suggestions. It uses Groq with `meta-llama/llama-4-scout-17b-16e-instruct`.

**Input parameters:**
- `new_item` (`dict`): The selected listing dictionary from `search_listings`.
- `wardrobe` (`dict`): A wardrobe dictionary containing an `items` list using the provided wardrobe schema.

**What it returns:**
A non-empty `str` describing one or two outfits centered on the thrifted item. When the wardrobe has saved pieces, the prompt asks the model to use their exact names. When the wardrobe is empty, it gives general styling advice without pretending the user owns anything.

**What happens if it fails or returns nothing:**
If `new_item` is invalid, the tool returns a descriptive error string. If the wardrobe is empty, it still calls the LLM for useful general styling advice. If the Groq call fails or returns empty text, the tool returns a readable error message rather than raising an uncaught exception. The planning loop detects that error and ends the interaction before creating a fit card.

---

### Tool 3: create_fit_card

**What it does:**
Uses the outfit suggestion plus the selected thrifted listing to generate a short, casual social-media caption. It also uses Groq with a higher temperature so captions can vary naturally.

**Input parameters:**
- `outfit` (`str`): The complete outfit suggestion returned by `suggest_outfit`.
- `new_item` (`dict`): The selected thrift listing dictionary.

**What it returns:**
A `str` containing a 2–4 sentence shareable fit caption that mentions the item, its price, its platform, and the overall outfit vibe.

**What happens if it fails or returns nothing:**
If the outfit is empty, the function returns `"I need a complete outfit suggestion before I can create a fit card."` If the selected item is missing, it returns a similar descriptive error. If the Groq request fails or returns no text, it returns an informative error string instead of crashing. The planning loop stores that message in `session["error"]`.

---

### Additional Tools

No additional tools are required for the base implementation. Query parsing is a helper inside `agent.py`, not a separate agent tool.

---

## Planning Loop

The planning loop uses the current session state to decide what happens next rather than blindly calling every tool.

1. Initialize a new session containing the original query, wardrobe, empty parsed parameters, empty search results, and `None` values for later outputs.
2. If the user query is empty, set `session["error"]` and return immediately.
3. Parse the query with regular expressions. Extract a maximum price from phrases such as `under $30` and a size from phrases such as `size M`. The remaining text becomes the item description. Store all three values in `session["parsed"]`.
4. Call `search_listings(description, size, max_price)` and store the returned list in `session["search_results"]`.
5. Check the search result. If it is empty, create an actionable error message and return the session immediately. This is the main conditional branch proving that the agent does not always run all three tools.
6. If matches exist, choose the first/highest-ranked result and store that exact dictionary in `session["selected_item"]`.
7. Call `suggest_outfit(session["selected_item"], session["wardrobe"])`. Store the string in `session["outfit_suggestion"]`. If the tool returned an error string or empty output, store it as the session error and stop.
8. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. Store the output in `session["fit_card"]`. If that tool reports an error, also store it in the session error field.
9. Return the completed session.

The loop is finished when either an error causes early termination or all three required tools have completed successfully.

---

## State Management

A Python dictionary returned by `_new_session()` is the single source of truth for one interaction. It stores:

- `query`: the original natural-language request.
- `parsed`: `description`, `size`, and `max_price` extracted from the query.
- `search_results`: the complete ranked list returned by `search_listings`.
- `selected_item`: the exact first listing dictionary selected from `search_results`.
- `wardrobe`: the wardrobe chosen in the Gradio interface.
- `outfit_suggestion`: the exact string returned by `suggest_outfit`.
- `fit_card`: the exact string returned by `create_fit_card`.
- `error`: `None` on success or a readable explanation when the workflow stops early.

State passes directly between tools. For example, `session["selected_item"]` is passed into `suggest_outfit`, and then both `session["outfit_suggestion"]` and the same `session["selected_item"]` are passed into `create_fit_card`. The user does not have to enter those values again.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the description/size/price constraints | Store a message explaining that no listing matched and suggest broadening the description, changing size, or raising the price limit. Stop before `suggest_outfit`. |
| `suggest_outfit` | Wardrobe is empty | Continue successfully by asking the LLM for general styling ideas without claiming the user owns specific pieces. |
| `suggest_outfit` | Missing item or LLM/API failure | Return a descriptive error string; the planner stores it in `session["error"]` and stops before `create_fit_card`. |
| `create_fit_card` | Outfit input is missing or incomplete | Return a descriptive error string rather than throwing an exception; the planner stores it as the session error. |
| `create_fit_card` | LLM/API failure | Return an informative error string so the UI remains usable instead of crashing. |

---

## Architecture

```mermaid
flowchart TD
    U[User query + wardrobe choice] --> P[Planning Loop]
    P --> Q[Parse description / size / max_price]
    Q --> S[search_listings]
    S --> SR[(Session: search_results)]
    SR --> C{Any results?}
    C -- No --> E1[Set session.error with suggestions]
    E1 --> R[Return session]
    C -- Yes --> SI[(Session: selected_item = results[0])]
    SI --> O[suggest_outfit]
    O --> OS[(Session: outfit_suggestion)]
    OS --> OE{Outfit tool succeeded?}
    OE -- No --> E2[Set session.error]
    E2 --> R
    OE -- Yes --> F[create_fit_card]
    F --> FC[(Session: fit_card)]
    FC --> FE{Fit card succeeded?}
    FE -- No --> E3[Set session.error]
    E3 --> R
    FE -- Yes --> R
    R --> UI[Gradio output panels]
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I will use ChatGPT. For each required function, I will provide the corresponding Tool section above plus the starter function signature and docstring from `tools.py`. I will ask it to implement only that function while preserving the provided signature and using `load_listings()` for mock data. I will verify `search_listings` with successful, no-result, price-filter, and size-filter tests. For the LLM tools, I will verify both normal behavior and the required failure paths with pytest mocks so testing does not depend on making real API calls.

**Milestone 4 — Planning loop and state management:**

I will give ChatGPT the Planning Loop, State Management, and Architecture sections above plus the starter `agent.py`. I expect it to preserve `_new_session()`, parse the query, branch after search, store each result in the correct session key, and stop early after failures. I will verify the generated logic with a test that forces `search_listings` to return `[]` and asserts that `suggest_outfit` is never called, plus another test that checks the exact selected-item object is passed through both later tools.

For `app.py`, I will provide the existing `handle_query()` TODO and the session field definitions. I will verify that errors appear only in the first panel and that successful sessions populate all three panels.

Before accepting AI-generated code, I will compare function signatures against this plan and run `python -m pytest tests/` from the repository root.

---

## A Complete Interaction (Step by Step)

**Example user query:** `"I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"`

For the implemented parser and UI, the clean searchable query used in the demo will be `"vintage graphic tee under $30"`; the wardrobe preference comes from the selected example wardrobe rather than being parsed from the sentence.

**Step 1:**
The agent parses the search query into approximately:

```python
{
    "description": "vintage graphic tee",
    "size": None,
    "max_price": 30.0,
}
```

It calls:

```python
search_listings("vintage graphic tee", size=None, max_price=30.0)
```

The results are stored in `session["search_results"]`. A high-ranked matching graphic/band tee becomes `session["selected_item"]`.

**Step 2:**
Because a listing was found, the planner calls:

```python
suggest_outfit(session["selected_item"], session["wardrobe"])
```

With the example wardrobe, the LLM can reference saved pieces such as the baggy dark-wash jeans, chunky white sneakers, black denim jacket, combat boots, or crossbody bag. The returned styling text is stored in `session["outfit_suggestion"]`.

**Step 3:**
If the outfit tool succeeds, the planner calls:

```python
create_fit_card(
    session["outfit_suggestion"],
    session["selected_item"],
)
```

The result is stored in `session["fit_card"]`.

**Final output to user:**
The Gradio app shows three panels: the selected listing and its details, the generated outfit idea, and the final shareable fit card. If Step 1 had returned no results, only a helpful search error would appear and Steps 2–3 would not run.
