# Privacy

What leaves the browser depends on the mode.

| Mode | What is sent | To whom |
|---|---|---|
| Blocking (default) | the text of other people's public comments and danmaku on pages you visit | your tonedown server, which forwards it to the Jev API |
| Composer self-check | your own draft, while you type (debounced) | same path |
| Local backend | nothing leaves your machine | a tonedown server on localhost running Qwen3Guard or the lexicon |

The server stores nothing but the verdict cache (hashes and probabilities, never the text) and,
only when a client posts feedback, the feedback line. Turn caching off with an in-memory cache.

The userscript keeps a cache of normalized text to verdict in Tampermonkey storage, on your machine.
