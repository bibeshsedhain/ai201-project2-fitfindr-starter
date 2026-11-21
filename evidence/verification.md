# Verification and submission readiness

Audit/implementation date: November 17, 2026. Starting upstream revision: cf75896.
Publication update (November 21, 2026): the implementation and student-provided
recording are included in the GitHub publication change.

## Checks completed

- `python -m pytest tests/ -q`: **39 passed** (Python 3.14.6).
- Installed the project requirements in a clean virtual environment. Gradio 6.32.0,
  Groq client 0.15.0, pytest 9.2.0 were used for verification.
- Gradio launched on localhost; `gradio_client.Client.predict` exercised actual
  HTTP callbacks. Happy-path fixture output populated all three panels; the
  no-results callback returned actionable advice and empty outfit/card panels.
  Repeat with `python scripts/smoke_ui.py`. This checks HTTP wiring, not visual
  screenshot QA or real model generation.
- Live Who What Wear RSS check returned `status=ok`, 50 recent posts checked,
  size-M listing matches, dated source links and observed style mentions. The
  feed was about 3 MB; the initial 2 MB cap was revised to a bounded 8 MB.
  This is a time-dependent sample, not a guarantee of future feed availability.
- Deliberately injected actual RuntimeError at the model-call boundary; outfit
  failure stopped card creation, and card failure preserved the successful outfit.
- `git diff --check` passed.

## Required rubric coverage in source and documents

- Three named tools: exact parameter names/types and concrete return contents in
  README and planning.md. All three called in one successful interaction.
- End-to-end workflow: natural-language query to fit card in agent.py and
  scripts/demo.py; the README walkthrough explains each tool's purpose.
- State: identity assertions in test_agent_happy_path_state_flow prove that the
  selected dict and returned outfit flow directly into later tools.
- Adaptive planning: empty query returns before tools; empty search retries once
  only when size exists; exhausted search stops; model failure skips later tools.
- Errors: per-tool descriptions, actual injected provider exceptions and
  actionable recovery messages; incomplete caption input handled explicitly.
- planning.md: inventories, conditional branches, state, error table, exact query
  walkthrough, text-based architecture diagram and section-specific AI Tool Plan.
- README: inventory, loop/state, failures, test examples, reflection and AI usage.
  Student review of the AI usage narrative remains necessary, as described below.

## Stretch coverage

- Price comparison: same category/shared tag, exclude self, two-peer minimum,
  median/percentage estimate, advisory failure; tested against known peer prices.
- Style memory: explicit saved wardrobe/preferences/defaults; disk reload in a
  separate store instance, query override tests and save/load/delete UI callbacks.
- Trend awareness: real public fashion platform RSS, recent source dates, mention
  counts and inventory matches in requested size; mocked failures/old posts tested.
  This is fashion editorial evidence, not a social-platform popularity API.
- Retry/fallback: at most one retry removing size, unchanged price ceiling, visible
  notices and selected actual size; exact call arguments tested.

The supplied course text does not assign individual bonus weights. This evidence
supports review; it does not certify 25/25 or 7/7.

## Remaining before submission

1. Live Groq generation was verified during the recording follow-up after the
   user configured their local key. The captured normal searches used real model
   calls; captions varied across the selected items and wardrobe modes. Review the
   results yourself before submission.
2. Review the code and AI usage narrative yourself. Replace or clarify inherited
   first-person accounts to reflect what you actually reviewed/revised/overrode.
3. The student-provided 3:55 recording is stored at media/fitfindr-demo.mp4 and
   linked directly from README. Its original audio is retained. Review the final
   recording before submission.
4. Submit the GitHub repository URL, planning.md and the linked video through the
   course portal after publication.
5. If your instructor interprets the trend stretch as specifically social posts,
   confirm that the public fashion editorial RSS platform is acceptable.

## Recording follow-up

- A 3:54 silent MP4 records the real browser app, including live Groq searches,
  all three required tools, the four stretch features, an empty wardrobe and an
  explicitly labeled provider exception test. A timestamped voice-over script is
  delivered beside the video. Add your narration and host/link the finished video.
- Browser capture exposed Gradio's blank text values arriving as None. Normalized
  empty style preferences in both search and profile save callbacks and added
  test_gradio_blank_optional_fields_are_none; all 39 tests passed after the fix.
- scripts/recording_app.py builds the same app with an additional recording-only
  failure-injection control. Only that control patches the model-call boundary to
  raise RuntimeError; ordinary searches use the configured live provider.
- Encoding contains a video stream only. Browser-only capture excludes unrelated
  tabs, desktop windows and credentials. Short pauses between recording sections
  were omitted; the live app outputs were not replaced or fabricated.

## Student recording publication — November 21, 2026

The student supplied a 3:54.87 MOV recording with an AAC audio track and explicitly
requested GitHub publication plus a direct README link. Converted it to H.264 MP4
without trimming or changing the original audio. README includes the direct video
URL, duration and approximate rubric-aligned navigation cues.
