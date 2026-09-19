# Contributing

```
uv sync --all-packages          # installs core, server and dev tools into .venv
uv run pytest                   # unit tests, no network, no API key
uv run ruff check .
node --check extension/userscript/tonedown.user.js
uv run eval/run_eval.py         # needs TYPESAFE_API_KEY in .env; costs a fraction of a cent
```

Good first contributions: a golden-set line for a misjudgment you saw (with the language and the
level you expected), a lexicon entry, a site adapter, a translation of the userscript UI strings.

Rubric wording changes must bump `RUBRIC_VERSION` in `schema.py`; it invalidates every cache.
