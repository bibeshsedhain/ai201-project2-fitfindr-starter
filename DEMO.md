# 3–5 minute recording checklist

Set GROQ_API_KEY in .env and launch `python app.py`. Use a screen recorder and
speak in your own words. Hide credentials; no key needs to appear on camera.

- **0:00–1:15:** Search `I'm looking for a vintage graphic tee under $30` with
  the example wardrobe. Narrate search selecting a listing, the price comparison,
  the same listing flowing to suggest_outfit, and the exact outfit flowing to
  create_fit_card. Show all three panels and the visible tool trace.
- **1:15–2:00:** Search `graphic tee size XXS under $30`. Show two search calls,
  unchanged budget and warning that the returned size differs. Explain the
  condition that triggers retry; the happy path only searched once.
- **2:00–2:45:** Save a profile with a changed wardrobe, preferences and defaults.
  Restart the app or use a new session and Load the same profile. Search without
  retyping those details. Show the loaded preferences influencing the outfit.
- **2:45–3:15:** Enable the public fashion-post check. Show checked time, dated
  source links and matching listing IDs in the requested size. Explain that
  these are editorial mentions matched to inventory, not global popularity.
- **3:15–4:00:** Run `python scripts/demo.py --offline` and show its explicitly
  labeled deliberate failure section. An injected RuntimeError breaks the real
  model-call boundary; the planner retains the listing, explains how to recover
  and never calls create_fit_card. Alternatively stop/restart your app with an
  intentionally invalid key and show the same recovery in the UI.
- **4:00–4:30:** Show the no-results ballgown query and point to planning.md's
  branch diagram and error table. Briefly explain what you reviewed/changed in
  the AI output. Replace README's video placeholder with the recording URL.

Offline fixture text is test evidence. Record a successful real Groq interaction
for the main demo and review actual caption specificity and variation yourself.
