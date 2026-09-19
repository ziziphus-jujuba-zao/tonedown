# HTTP API

Interactive docs at `/docs` when the server runs.

## POST /v1/grade

```json
{
  "items": [
    {"id": "c1", "text": "楼主就是个傻X", "lang": "zh"},
    {"id": "c2", "text": "Great episode!"}
  ],
  "policy": "balanced"
}
```

`policy` is optional: a built-in name (`strict`, `balanced`, `relaxed`) or a full policy object.
Tenants can have a default policy; the request value wins.

```json
{
  "results": [
    {"id": "c1", "text_hash": "…", "lang": "zh", "level": 2.0, "level_argmax": 2,
     "level_probs": [0, 0, 1, 0, 0], "categories": {"harassment": 0.97, "spam": 0.01, "…": 0},
     "targeted": 0.94, "confidence": 0.99, "backend": "jev:jev-latest", "cached": false,
     "input_tokens": 410.5, "reasons": [], "action": "review"}
  ],
  "policy": "balanced", "backend": "jev:jev-latest",
  "usage": {"items": 2, "cached": 0, "backend_input_tokens": 821.0}
}
```

Auth: `X-API-Key: <key>` or `Authorization: Bearer <key>`. With `TONEDOWN_API_KEYS` empty the server
is open (local development, or a proxy you rate-limit some other way).

Errors: 400 unknown policy, 401 missing or unknown key, 413 too many items or text too long,
429 rate limited, 502 backend failure (never a fabricated verdict).

## GET /v1/policies

Built-in policies with their thresholds.

## POST /v1/feedback

```json
{"text_hash": "…", "human_action": "pass", "expected_level": 0, "note": "sarcasm, not an insult"}
```

Appends one JSON line to `TONEDOWN_FEEDBACK_PATH`. Feed those lines into the golden set.

## GET /healthz

Backend name, default policy, version.
