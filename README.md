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
| User-side blocking (Tampermonkey userscript for Bilibili and YouTube) | `extension/userscript` | Bilibili danmaku verified in a headless browser; comment and YouTube selectors not yet verified live |
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
| 0 | safe | opinions, jokes, harsh criticism of a work, memes, laughter and screaming, repeated characters |
| 1 | mild | mild profanity, a rude tone, mocking an opinion |
| 2 | moderate | insults at a person, scam or ad spam, crude sexual remarks |
| 3 | severe | hate speech, sexual content involving minors or non-consent, glorifying violence, doxxing, selling drugs or weapons |
| 4 | dangerous | credible threats, expressing or encouraging suicide or self-harm, instructions enabling serious harm |

Categories: spam, harassment, hate, sexual, violence, self_harm, illegal, plus a *targeted* flag for
attacks on a specific person.

## Accuracy

The rubric and every instruction are written in English, and English is the primary language. The
same rubric also grades Chinese, Japanese, Korean, Spanish, Russian, Arabic, German, French,
Vietnamese and Hindi. The golden set holds 74 hand-written comments and danmaku, the bullet comments
that scroll across videos on Bilibili and similar sites. Results with Jev `jev-latest` and the
`balanced` policy (`uv run eval/run_eval.py --backend jev`):

| exact level | within ±1 | F1 (level ≥ 2) | categories | targeted | false blocks | misses |
|---|---|---|---|---|---|---|
| 74 / 74 | 74 / 74 | 1.00 | 73 / 74 | 74 / 74 | 0 | 0 |

What the set checks, English cases first:

| Case | Example | What it means | Expected |
|---|---|---|---|
| Criticism of a work | Honestly the writing this season is lazy and boring | criticizes the show, not a person | 0 safe |
| Mocking an opinion | this take is so dumb lol | rude, but does not insult the person | 1 mild |
| Insult | OP is a brainless idiot, go touch grass | attacks the original poster | 2 moderate |
| Scam spam | Make $3000/day from home!! DM me now, limited spots | advertising | 2 moderate |
| Hate | People from that country are all thieves and should be kicked out | attacks a whole group | 3 severe |
| Implied threat | I know where you live, you'd better watch your back tomorrow | a threat that never says "kill" | 4 dangerous |
| Abbreviated incitement | nobody would miss you, just kys already | kys means "kill yourself" | 4 dangerous |
| Pinyin initials | 楼主nmsl, 编剧就是个sb | Chinese insults typed as initials: nmsl is "your mom is dead", sb is a vulgar "idiot" | 2 moderate |
| Slang that only looks like abuse | 这剧yyds，笑死我了 | yyds is "eternal god", praise like "the GOAT"; 笑死我了 is "I'm dying of laughter" | 0 safe |
| Look-alike character | 主播傻β一个 | a Greek β replaces the B in 傻B ("idiot") to slip past word filters | 2 moderate |
| Danmaku idioms | 火钳刘明, 前方高能 | a deliberate misspelling of "leaving my name before this blows up", and "big moment coming up" | 0 safe |
| Laughter and screaming | 哈哈哈哈哈…, 啊啊啊啊啊… | "hahaha…" and "aaaah…" | 0 safe |

Ordinary danmaku are the hard part, because memes, laughter and reaction noise look like spam or
abuse to a literal reader. An earlier version of the rubric flagged 24 to 28 of 30 such danmaku at
the strictest setting. The current one flags 6, all opinions with a negative edge, and every batch
tells the model that the texts are comments and danmaku under videos.

With the full nine-question rubric a comment costs 600 to 650 input tokens, about 0.025 USD per 1,000
comments before caching, and 20 to 200 ms per item when batched. Threats outside English and Chinese
can land at 3.2 to 3.8 instead of 3.9, so policies trigger on level 3 and above. A set this small
proves the pipeline, not the model. Grow `eval/golden` before trusting thresholds in production.

## Prior art

Jigsaw's *Tune* (2019, discontinued; Perspective API sunsets after 2026), Azure AI Content Safety
(severity 0-6), 阿里云内容安全 (pass / review / block), Qwen3Guard (safe / controversial / unsafe,
Apache 2.0). Bilibili's own filters and the popular userscripts work on keywords, density and reports,
not on meaning.

## License

Apache-2.0. See `docs/` for architecture, API, adapters, privacy and roadmap.
