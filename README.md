# FitFindr 🛍️

Find a secondhand piece, compare its price, style it with your wardrobe, and turn
that outfit into a shareable fit card. The agent branches on tool results, retains
state between calls, and includes all four stretch implementations.

## Setup and run

Python 3.10+ is required (verified here with Python 3.14.6).

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env and set your own GROQ_API_KEY.
python -m pytest tests/ -q
python app.py
```

Open the local URL printed by Gradio. The two generative tools require a real Groq
key; listing search, price comparison and saved profiles work without one.
`GROQ_MODEL` defaults to `openai/gpt-oss-20b`. The original course model,
`meta-llama/llama-4-scout-17b-16e-instruct`, was shut down July 17, 2026 according to
[Groq's deprecation documentation](https://console.groq.com/docs/deprecations).
The replacement appears in the [current model catalog](https://console.groq.com/docs/models).
Override `GROQ_MODEL` with an available model for your account. No key is included.

## Submission status

The source, tool tests, README and root `planning.md` cover the required workflow
and four stretch features. Verification details and remaining submission steps
are in `evidence/verification.md`. This is not a guarantee of a rubric score.

**Project demo:** [Watch the recording (3:55, with audio)](https://github.com/bibeshsedhain/ai201-project2-fitfindr-starter/raw/refs/heads/main/media/fitfindr-demo.mp4).
The recording is linked again in the Demo Video section with rubric-aligned
navigation cues. Review the code, AI usage account and final recording, then
submit the repository and video links through the course portal.

## Tool inventory

### `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

`description` is the item/style search text; `size` is an optional whole-token size
such as `M` or `8`; `max_price` is an optional inclusive price ceiling in dollars.
Loads mock listings with `load_listings()`, applies size/price filters, then ranks
weighted keyword overlap (title/category before style/description). Returns a
ranked list of dictionaries with `id` (str), `title` (str), `description` (str),
`category` (str), `style_tags` (list[str]), `size` (str), `condition` (str),
`price` (number), `colors` (list[str]), `brand` (str or None), `platform` (str).
Returns `[]` for blank text, no matches or a dataset read failure. Invalid prices
are skipped. Letter sizes match `S/M` but never arbitrary letters in `One Size`.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

`new_item` is the selected listing dictionary; `wardrobe` contains `items`
(list[dict] with name/category/colors/style_tags) and optional `style_preferences`
(str). Calls Groq for one or two complete outfit suggestions, referencing exact
wardrobe names. Empty wardrobes receive general pairing advice without claims of
ownership. Returns the outfit string or an actionable error string on an invalid
item, empty model response or provider failure. The planner stops on errors.

### `create_fit_card(outfit: str, new_item: dict) -> str`

`outfit` is the exact successful styling string; `new_item` is the same selected
listing. Calls Groq at temperature 1.0 for a 2–4 sentence social caption grounded
in the outfit, item name, price and platform. Returns the caption string or an
error string for missing inputs, empty output or provider failure. Different
input item/outfit details are included in the prompt; creative variation requires
live review, not an assertion that random generation can never repeat.

### `compare_prices(new_item: dict) -> dict` — stretch

`new_item` is the selected listing. Compares other IDs in the same category with
at least one shared style tag. Returns `status` (ok/insufficient_data/unavailable),
`comparable_ids` (list[str]), `count` (int), `median_price` (float or None),
`difference_pct` (float or None), `verdict` (str), `message` (str).
At least two peers are required. Prices more than 15% below/above their median are
labeled below/above typical; otherwise fair. This is a mock-dataset estimate;
condition, brand, shipping and measurements are not controlled. Failure is advisory
and does not stop styling.

### `check_trends(size: str | None = None) -> dict` — stretch

`size` optionally filters mock inventory availability. Downloads the public
[Who What Wear RSS feed](https://www.whowhatwear.com/feeds.xml) with an 8-second
timeout and an 8 MB limit. Counts dataset style-tag mentions in titles,
descriptions and categories from posts published within the last 30 days. Returns
`status` (ok/empty/unavailable), `source` (URL str), `checked_at` (UTC ISO str),
`window_days` (int), `size` (str or None), `posts_checked` (int), `trends`
(list[dict]), and `message` (str). Each trend has `style` (str), `post_count` (int),
`listing_ids` (list[str] matching size), `sources` (up to three dicts with `title`,
`url`, `published_at`, all str). Up to five styles are returned, ordered by count.
Duplicate links count once per style. Old/future/undated posts are excluded.

This is a small editorial mention sample with size-filtered inventory, not a
claim about global popularity or the authors' sizes. It is an optional live UI
checkbox; blocked feeds, malformed XML and no evidence never produce invented trends.

## Planning loop and state management

`run_agent(query: str, wardrobe: dict, profile: dict | None = None,
include_trends: bool = False) -> dict` implements conditional orchestration:

1. Empty query or invalid profile: set `error` and return before tools.
2. Parse description, `size M`/numeric size and `under $30`/similar budget phrases.
   Fill omitted size/budget from a validated loaded profile. Explicit query values win.
3. Search; record parameters and result count in `search_attempts`.
4. If results are empty **and size exists**, retry exactly once with `size=None`,
   keeping description and budget. Record a notice that size was removed and that
   measurements must be checked. Never increase the budget automatically.
5. If results remain empty, return an actionable search message; no styling or
   fit-card tools run. If no original size existed, there is no retry.
6. Store `selected_item = search_results[0]`. Run advisory `compare_prices`.
   Run advisory `check_trends` only when explicitly enabled.
7. Pass the exact `selected_item` object and wardrobe to `suggest_outfit`.
   Store `outfit_suggestion`; an empty/error string ends the workflow.
8. Pass that exact outfit string and item object to `create_fit_card`.
   Store `fit_card` only on success. On failure keep the listing and valid outfit.

Session fields: `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`,
`outfit_suggestion`, `fit_card`, `error`, `notices`, `search_attempts`, `tool_calls`,
`price_comparison`, `trends`. The user never re-enters intermediate outputs.
`tool_calls` exposes the actual branch taken in the first UI panel; `notices`
shows retry adjustments. Prices/trends are advisory and do not rewrite selected
items or outfit state. The session is transient; only explicitly saved profiles
persist across application restarts.

## Style profile memory — stretch

Expand the profile section, edit the wardrobe JSON, preferences, default size and
budget, and **Save profile** under a local name. Later, even after restarting the
app, enter the same name and **Load profile**. Loading fills the editor and selects
`Custom / saved wardrobe`; the next query uses those values without re-entry.
Selecting the example or empty wardrobe intentionally uses that wardrobe instead.
Save always stores the wardrobe editor; changes persist only when Save is clicked.
Preferences apply in every wardrobe mode, and explicit query size/budget override defaults.

`ProfileStore.save(profile_id: str, profile: dict) -> dict` validates and atomically
writes a version-1 JSON profile. `load(profile_id: str) -> dict | None` returns the
validated profile or None if absent. `delete(profile_id: str) -> None` removes it.
Saved fields are `wardrobe`, `style_preferences`, `size`, `max_price`, and `version`.
Files live under ignored `.fitfindr/profiles/` (override with
`FITFINDR_PROFILE_DIR`). Names are hashed to filenames so paths cannot escape the
folder. Names are local identifiers, not authentication; this is a local demo,
not a shared multi-user hosting service. Delete removes disk data; loaded editor
values remain until cleared. No API key or search history is saved.

## Complete interaction

For `I'm looking for a vintage graphic tee under $30` and the example wardrobe:

1. Parse `description="a vintage graphic tee"`, `size=None`, `max_price=30.0`.
   `search_listings` is needed to identify an actual item; save its ranked results.
2. Select the first dictionary, then call `compare_prices(selected_item)` to
   estimate fairness. The fixture dataset currently selects `lst_006`,
   `Graphic Tee — 2003 Tour Bootleg Style`, $24 on depop, size L.
3. Call `suggest_outfit(selected_item, wardrobe)` because a listing exists. The
   prompt includes baggy dark-wash jeans, chunky white sneakers and other owned
   pieces; save the actual returned string without rewriting it.
4. Call `create_fit_card(outfit_suggestion, selected_item)` because the outfit
   succeeded. Show the listing, price estimate, outfit and shareable caption.
   With live trends enabled, an additional advisory feed check occurs before styling.

For `graphic tee size XXS under $30`, two search calls occur: XXS, then no size
filter. Both retain $30. The returned actual size is shown with a warning.
For `designer ballgown size XXS under $5`, both searches are empty and the agent
stops before any Groq call. These source paths and tests demonstrate adaptation.

## Error handling and deliberate failure evidence

- **Search:** empty result/read failure returns `[]`; retry once without size if
  applicable, then say what constraints failed and suggest a broader description,
  different size or higher user-chosen price limit. Check `data/listings.json` if
  known listings also fail. Never style an absent item.
- **Outfit:** invalid item returns a request for a valid listing. Empty wardrobe
  is recoverable through general advice. Empty model output asks to retry; a
  provider failure says to check `GROQ_API_KEY`, `GROQ_MODEL`, connection and Groq
  limits, then retry. No fit card is called; the selected listing remains visible.
- **Fit card:** empty outfit returns `I need a complete outfit suggestion before I
  can create a fit card.` Missing item requests the selected thrifted item.
  Provider failure gives a credential/model/connection/limits checklist and keeps
  the valid outfit available. Error text is never displayed as a successful caption.
- **Price/trends:** return unavailable/insufficient/empty status with advice, and
  continue the required workflow. Trends never use an undated cached fallback.
- **Profiles:** invalid JSON/schema, missing profile or disk errors produce a
  corrective UI message; a failed load preserves existing editor values.

`test_actual_outfit_api_failure_stops_card` deliberately raises RuntimeError from
the model call (an actual exception, not merely an empty search). It asserts the
actionable credential message and that the card is never called.
`test_actual_card_api_failure_preserves_outfit` injects a card-service failure and
asserts the valid outfit survives. `test_ui_retains_partial_results` verifies this
recovery reaches the UI. See the reproducible log in `evidence/offline-demo.txt`.

## Verification

```bash
python -m pytest tests/ -q
python scripts/demo.py --offline
python scripts/demo.py --offline --live-trends
# With your configured key, use real model calls:
python scripts/demo.py --live-trends
```

Offline mode explicitly labels model text as fixtures. Tests check all required
interfaces, empty/malformed inputs, size and budget filtering, object identity,
conditional early stops, bounded retry arguments, price median/excluded self,
profile persistence and override precedence, sourced recent trends and failures,
and Gradio callbacks. `evidence/verification.md` records the actual checks run.

## Spec reflection

The spec's explicit state handoffs helped preserve the exact listing object and
outfit string across calls; identity/call-argument assertions verify this. The
stretch plan was added to `planning.md` before stretch implementation, then the
final branches and diagram were synchronized with the code.

Divergences: a deterministic regex helper parses common size/budget phrasing
instead of spending another LLM call. It does not infer a full wardrobe from
arbitrary prose; enter it in the profile editor. Scout was replaced because it
is retired. Trend evidence comes from public fashion editorial posts and maps to
local size availability, since those posts do not reliably include garment sizes.
The initial 2 MB feed limit was raised to 8 MB after a live feed exceeded it.

## AI usage and review

The two original implementation accounts below were present in the supplied repo.
The student should verify that they accurately describe their own work:

1. **Required tools:** ChatGPT was directed with starter signatures, the Tool
   Inventory requirements and mock schema to preserve interfaces, reuse
   `load_listings()` and call Groq only for generative tools. The prior account
   describes review of size matching for combined sizes such as `S/M`.
2. **Planner:** ChatGPT was directed with `agent.py`, session fields and
   planning/error requirements to branch on results and carry state. The prior
   account describes review using mocked empty-search and exact-object tests.

**This stretch implementation session used Codex:**

3. The student asked Codex to audit the supplied project rubric and implement
   stretch goals. Codex used `planning.md` Tools, Planning Loop, State Management,
   Error Handling and Architecture sections plus the supplied Stretch Features.
   Codex drafted the stretch plan before code, implemented all four features and
   reviewed exact interfaces and state identity with pytest. Codex revised the
   original size regex so letters in `One Size` no longer satisfy `S`/`M` filters,
   retained budget during retry, and preserved partial UI results after failures.
4. Codex was directed by the same request to confirm readiness. It checked provider
   docs and a live feed, replaced the retired model default, revised the feed limit
   after live testing, and added reproducible failure evidence. These are agent
   reviews, **not a claim of student review**. Before submission, describe the
   actual changes you reviewed, revised or overrode in your own words.

## Demo Video

[**Watch/download the FitFindr project demo — 3 minutes 55 seconds, with audio**](https://github.com/bibeshsedhain/ai201-project2-fitfindr-starter/raw/refs/heads/main/media/fitfindr-demo.mp4)

[Video file in this repository](media/fitfindr-demo.mp4)

This is the student-provided recording, converted from MOV to a smaller MP4 with
its original audio retained. Its 3:55 duration meets the required 3–5 minute range.
The following approximate cues locate the assignment's required demonstrations:

- **0:00–0:12:** Introduction to the agent.
- **0:12–0:35:** A natural-language request goes through `search_listings`,
  `suggest_outfit` and `create_fit_card`, ending in a complete fit card.
- **0:35–0:57:** State management: the same selected item and returned outfit pass
  between tools without re-entry; the price comparison is also explained.
- **0:57–1:20:** No-results branch: the planner stops after search attempts instead
  of unconditionally calling the outfit and caption tools.
- **1:20–1:46:** Retry fallback: only size is relaxed, the original budget is
  retained, and the actual returned size is disclosed.
- **1:46–2:09:** Empty-wardrobe handling gives general styling advice.
- **2:09–2:40:** Save a style profile and restore it after reloading the page.
- **2:40–3:23:** Use saved wardrobe/defaults and show live trend evidence with
  dated sources and size-filtered inventory.
- **3:23–3:55:** Deliberately injected provider exception: the selected listing
  remains available, recovery steps are actionable, and `create_fit_card` is not
  called after outfit generation fails.

Normal searches in the demonstrated app use live Groq. The final failure control
is explicitly labeled and injects an exception at the model-call boundary; it is
not presented as an unplanned service outage. The recording harness is available
in `scripts/recording_app.py`.
