# ToneDown

[![ci](https://github.com/ziziphus-jujuba-zao/tonedown/actions/workflows/ci.yml/badge.svg)](https://github.com/ziziphus-jujuba-zao/tonedown/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Set your own line.** Multilingual text safety grading for comments, danmaku and posts: a 0 to 4 scale from **safe** to
**dangerous**, per-category probabilities, and policies that turn them into *pass / review / block*
for platforms or *show / blur / hide* for users. Powered by [Jev](https://typesafe.ai) (TypeSafe's
System One model) with an offline lexicon fallback and an experimental local Qwen3Guard backend.

Platforms pick a policy, users pick a level, the engine only measures.

[中文说明](README.zh-CN.md)

| Surface | Package | Status |
|---|---|---|
| Engine (Python library + CLI) | `packages/core` | working |
| Platform API (FastAPI, Docker) | `packages/server` | working |
| User-side blocking (Tampermonkey userscript for Bilibili and YouTube) | `extension/userscript` | MVP, selectors not yet verified live |
| MV3 browser extension | `extension/mv3` | planned |

## Quick start

```bash
git clone https://github.com/ziziphus-jujuba-zao/tonedown.git && cd tonedown
cp .env.example .env            # paste your Jev key; skip it to use the offline lexicon only
uv sync --all-packages

uv run tonedown grade "楼主就是个傻X" "Great episode!" "お前の住所知ってるからな"
uv run tonedown-server         # http://127.0.0.1:8080/docs
uv run eval/run_eval.py         # per-language quality table on the golden set
```

Then [install the userscript](https://raw.githubusercontent.com/ziziphus-jujuba-zao/tonedown/main/extension/userscript/tonedown.user.js) with Tampermonkey or Violentmonkey, open a Bilibili or YouTube
video and click the round **TD** button bottom-right.

## The scale

| level | name | examples |
|---|---|---|
| 0 | safe | opinions, jokes, harsh criticism of a work |
| 1 | mild | rude tone, mild profanity, filler |
| 2 | moderate | insults at a person, scam or ad spam, crude sexual remarks |
| 3 | severe | hate speech, sexual content involving minors or non-consent, glorifying violence, doxxing, selling drugs or weapons |
| 4 | dangerous | credible threats, expressing or encouraging suicide or self-harm, instructions enabling serious harm |

Categories: spam, harassment, hate, sexual, violence, self_harm, illegal, plus a *targeted* flag for
attacks on a specific person.

## Measured on 2026-09-19

Golden set of 63 hand-written comments in 11 languages (zh, en, ja, ko, es, ru, ar, de, fr, vi, hi),
rubric in English, Jev `jev-latest`, policy `balanced` (`uv run eval/run_eval.py --backend jev`):

| exact level | within ±1 | F1 (level ≥ 2) | categories | targeted | false blocks | misses |
|---|---|---|---|---|---|---|
| 63 / 63 | 63 / 63 | 1.00 | 63 / 63 | 62 / 63 | 0 | 0 |

The set includes pinyin abbreviations (nmsl, sb), slang that only looks like abuse (yyds) and
homoglyphs (傻β). With the full nine-question rubric a comment costs 520 to 580 input tokens, about
0.02 USD per 1000 comments before caching, and 20 to 200 ms per item when batched. Threats outside
zh/en land at 3.2 to 3.8 rather than 3.9, so policies trigger on level 3 and above. A set this small
proves the pipeline, not the model: grow `eval/golden` before trusting thresholds in production.

## Prior art

Jigsaw's *Tune* (2019, discontinued; Perspective API sunsets after 2026), Azure AI Content Safety
(severity 0-6), 阿里云内容安全 (pass / review / block), Qwen3Guard (safe / controversial / unsafe,
Apache 2.0). Bilibili's own filters and the popular userscripts work on keywords, density and reports,
not on meaning.

## License

Apache-2.0. See `docs/` for architecture, API, adapters, privacy and roadmap.
