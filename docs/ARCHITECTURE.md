# Architecture

One engine, three surfaces, one data structure.

```
                    ┌───────────────────────── packages/core (tonedown) ─────────────────────────┐
 text ──▶ normalize ─▶ detect language ─▶ lexicon match ─▶ cache? ─▶ backend ─▶ Verdict ─▶ policy ─▶ action
                                                                    │
                                              ┌─────────────────────┼─────────────────────┐
                                        Jev (TypeSafe)         Qwen3Guard (local)     lexicon-only
                                        Score + Nouls          Safe/Controv./Unsafe   word lists
                    └──────────────────────────────────────────────────────────────────────────┘
        ▲                                   ▲
        │ HTTP /v1/grade                    │ Python import
 packages/server (FastAPI)           eval/run_eval.py
 tenants · rate limits · policies    golden set · public datasets
        ▲
        │ GM_xmlhttpRequest / fetch
 extension/userscript, extension/mv3 (later)
 adapters per site · slider · blur/hide · composer self-check
```

## Verdict

| field | meaning |
|---|---|
| `level` | expected level, 0 safe … 4 dangerous, probability-weighted |
| `level_argmax`, `level_probs` | most likely level and the full distribution |
| `categories` | probability per category: spam, harassment, hate, sexual, violence, self_harm, illegal |
| `targeted` | probability the text attacks a specific person |
| `confidence` | backend's confidence in the level |
| `lang`, `backend`, `cached`, `input_tokens`, `reasons` | provenance |
| `action` | pass / review / block once a policy has been applied |

The engine returns probabilities; policies (server side) and the slider (user side) turn them into
actions. That is why the same verdict can be blocked on one site and merely blurred by one user on
another.

## Why Jev

Jev answers many typed questions about one state in a single call, in parallel and in isolation, and
returns calibrated probabilities instead of prose. Sixteen comments with nine questions each is one
request of roughly half a second; input tokens cost 0.042 USD per million and output is free. The
rubric is written once in English and the content can be in any language.

## Multilingual strategy

- Rubric in English, content in any language. Criteria can carry per-language examples where a
  concept is culture-specific (regional discrimination, caste, religion).
- Language detection only chooses lexicons and routing; when it fails the page language or the user's
  setting wins. It never blocks grading.
- Normalization defeats cheap evasion: zero-width characters, full-width letters, Cyrillic and Greek
  look-alikes, spaced-out letters.
- Threats in languages other than zh/en tend to score 3.2-3.6 rather than 3.9: policies key on
  `level >= 3`, not on level 4 alone.
- Low confidence downgrades block to review. Silence is not a moderation outcome.
