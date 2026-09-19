# Browser tools

Two delivery forms share the same adapters and decision logic:

| Form | Status | Install |
|---|---|---|
| `userscript/tonedown.user.js` | working MVP | Tampermonkey / Violentmonkey: open [the raw file](https://raw.githubusercontent.com/ziziphus-jujuba-zao/tonedown/main/extension/userscript/tonedown.user.js), click install |
| `mv3/` WebExtension | not started (roadmap phase 4) | Chrome Web Store / Firefox Add-ons later |

## What the userscript covers

| Site | Surface | Adapter |
|---|---|---|
| bilibili.com video / bangumi / opus / dynamic | comments (new shadow-DOM UI and legacy UI) | `bilibili-comments` |
| bilibili.com video | on-screen danmaku | `bilibili-danmaku` |
| live.bilibili.com | live chat list | `bilibili-livechat` |
| youtube.com watch pages | comments and replies | `youtube-comments` |
| youtube.com live chat (the `/live_chat` iframe) | live chat messages | `youtube-livechat` |
| every matched site | composer self-check on `textarea` and `contenteditable` boxes | built in |

The Bilibili danmaku adapter was verified in a headless Chrome session on 2026-09-19 (reused player
elements are re-judged when their text changes; hiding survives the player's style rewrites). The
comment adapters and the YouTube adapters were written against the page structures as of September
2026 and are not yet verified live; if a site changes its markup, fix the adapter's `sweep()` and
report it with the misjudgment issue template.

## Setup

1. Run the server (`uv run tonedown-server`) or point the script at a hosted one.
2. Install the userscript, open a video page, click the round **TD** button bottom-right.
3. Set server URL and API key if the server requires one, press *Test connection*.
4. Move the slider: safe only, hide moderate and up (default), hide severe and up, hide dangerous
   only, show everything. The level just below your threshold is blurred with a label you can click
   to reveal. Danmaku elements are reused by the Bilibili player, so every element is re-judged
   whenever its text changes.

The API key never needs to be a Jev key: the server holds that. Give users a per-user server key, or
run the server on `localhost` with open access.
