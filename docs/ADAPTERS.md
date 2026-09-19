# Writing a site adapter (userscript)

An adapter is an object in the `adapters` array of `extension/userscript/tonedown.user.js`:

```js
{
  name: 'example-comments',
  kind: 'comment',                 // 'comment' hides with display:none; 'danmaku' hides with visibility:hidden
  active: () => location.hostname === 'example.com',
  hot: '#comments',                // optional: a container to watch closely for fast-appearing nodes
  sweep() {
    const out = [];
    for (const el of document.querySelectorAll('.comment')) {
      const body = el.querySelector('.comment-text');
      const text = body ? body.innerText.trim() : '';
      if (text) out.push({ node: el, container: el, labelHost: body, text });
    }
    return out;
  },
}
```

- `node` is the element used for de-duplication; return the same element on every sweep.
- `container` is what gets hidden; `labelHost` is what gets blurred and receives the "folded" chip.
- Shadow DOM: use `deepQueryAll(root, selector)`; see the Bilibili comments adapter.
- Keep `sweep()` cheap; it runs on every DOM change (debounced) and every 1.5 s.

Sites already covered: Bilibili comments, danmaku and live chat; YouTube comments and live chat.
Candidates: X, Reddit, Twitch chat, Niconico, Douyin web, Weibo.
