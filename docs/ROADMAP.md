# Roadmap

| Phase | Scope | Done when |
|---|---|---|
| 0 Foundations | repo, schema, rubric, Jev backend, golden set, eval harness | `run_eval.py` prints a per-language table |
| 1 Engine | pipeline, cache, policies, lexicon, normalize, CLI, tests, PyPI release | `pip install tonedown` then one command grades any language |
| 2 Platform API | FastAPI, tenants, rate limits, feedback, Docker, OpenAPI | `docker compose up` then `curl` grades |
| 3 User side | userscript for Bilibili and YouTube, slider, blur/hide, composer check | slider at "safe only" removes abusive danmaku on a busy video |
| 4 MV3 extension | same adapters as a WebExtension, X / Reddit / Twitch, store listings | installable from the Chrome Web Store |
| 5 Local mode | Qwen3Guard backend verified, language routing, public-dataset comparison in README | eval table with both backends |
| 6 Community | contributing guide, adapter template, misjudgment issues feeding the golden set, releases | first outside adapter merged |

Status on 2026-09-19: phases 0 to 3 scaffolded in one session; live-browser verification of the
userscript adapters and the Qwen3Guard backend are the first open items.
