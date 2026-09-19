// ==UserScript==
// @name         ToneDown
// @namespace    https://github.com/ziziphus-jujuba-zao/tonedown
// @version      0.2.0
// @description  Grade comments, danmaku and live chat from safe to dangerous, then hide or blur what you don't want to see. 弹幕、评论、直播聊天分级自我屏蔽，附发帖前自查。
// @author       ToneDown contributors
// @homepageURL  https://github.com/ziziphus-jujuba-zao/tonedown
// @supportURL   https://github.com/ziziphus-jujuba-zao/tonedown/issues
// @updateURL    https://raw.githubusercontent.com/ziziphus-jujuba-zao/tonedown/main/extension/userscript/tonedown.user.js
// @downloadURL  https://raw.githubusercontent.com/ziziphus-jujuba-zao/tonedown/main/extension/userscript/tonedown.user.js
// @license      Apache-2.0
// @match        https://www.bilibili.com/video/*
// @match        https://www.bilibili.com/bangumi/play/*
// @match        https://www.bilibili.com/list/*
// @match        https://www.bilibili.com/opus/*
// @match        https://t.bilibili.com/*
// @match        https://live.bilibili.com/*
// @match        https://www.youtube.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @connect      localhost
// @connect      127.0.0.1
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // ------------------------------------------------------------------ config
  const DEFAULTS = {
    server: 'http://127.0.0.1:8080',
    apiKey: '',
    enabled: true,
    hideLevel: 2,      // hide when level_argmax >= hideLevel (1..4); 5 = show everything
    blur: true,        // blur the level just below hideLevel instead of showing it plainly
    composer: true,    // grade your own draft before you post it
    allow: {},         // categories you never want hidden (except level 4), e.g. {harassment: true}
  };
  const cfg = Object.assign({}, DEFAULTS, safeParse(GM_getValue('tonedown.config', '{}'), {}));
  cfg.hideLevel = Math.min(5, Math.max(1, Number(cfg.hideLevel) || DEFAULTS.hideLevel));
  const saveCfg = () => GM_setValue('tonedown.config', JSON.stringify(cfg));

  const ZH = (navigator.language || '').toLowerCase().startsWith('zh');
  const T = ZH ? {
    title: 'ToneDown · 分级屏蔽', enabled: '启用', blur: '低一档的内容打码而不是隐藏', composer: '发帖前自查草稿',
    allow: '不屏蔽这些类别（危险级除外）', server: '服务器', key: 'API key', test: '测试连接', ok: '连接正常', fail: '连接失败',
    stats: (s) => `已评分 ${s.graded} · 隐藏 ${s.hidden} · 打码 ${s.blurred} · 缓存命中 ${s.cached}`,
    slider: ['只看安全', '隐藏 中度及以上', '隐藏 严重及以上', '只隐藏 危险', '全部显示'],
    folded: '已折叠', reveal: '点击查看', draft: '草稿等级', draftHint: '发出去可能被折叠或拦截',
  } : {
    title: 'ToneDown', enabled: 'Enabled', blur: 'Blur the level just below instead of showing it', composer: 'Check my draft before posting',
    allow: 'Never hide these categories (except dangerous)', server: 'Server', key: 'API key', test: 'Test connection', ok: 'Connected', fail: 'Connection failed',
    stats: (s) => `graded ${s.graded} · hidden ${s.hidden} · blurred ${s.blurred} · cache hits ${s.cached}`,
    slider: ['safe only', 'hide moderate and up', 'hide severe and up', 'hide dangerous only', 'show everything'],
    folded: 'Folded', reveal: 'click to reveal', draft: 'Draft level', draftHint: 'may be folded or blocked when posted',
  };
  const CAT = ZH
    ? { spam: '广告', harassment: '辱骂', hate: '仇恨', sexual: '色情', violence: '暴力威胁', self_harm: '自伤', illegal: '违法' }
    : { spam: 'spam', harassment: 'harassment', hate: 'hate', sexual: 'sexual', violence: 'violence', self_harm: 'self-harm', illegal: 'illegal' };
  const LEVEL = ZH ? ['安全', '轻微', '中度', '严重', '危险'] : ['safe', 'mild', 'moderate', 'severe', 'dangerous'];
  const LEVEL_COLOR = ['#2e7d32', '#8d9e2c', '#e0a100', '#e65100', '#b71c1c'];

  const stats = { graded: 0, cached: 0 };
  const isTop = window.top === window;

  // ------------------------------------------------------------------ cache
  // Keyed by normalized text. The key name carries a version so verdicts from an older rubric are dropped.
  const CACHE_KEY = 'tonedown.cache.v2';
  try { GM_deleteValue('tonedown.cache'); } catch (e) { /* older managers */ }
  const cache = new Map();
  for (const [k, v] of safeParse(GM_getValue(CACHE_KEY, '[]'), [])) cache.set(k, v);
  let cacheDirty = false;
  setInterval(() => {
    if (!cacheDirty) return;
    cacheDirty = false;
    const entries = Array.from(cache.entries());
    GM_setValue(CACHE_KEY, JSON.stringify(entries.slice(Math.max(0, entries.length - 3000))));
  }, 15000);

  const ZERO_WIDTH = new RegExp('[' + String.fromCharCode(0x200b) + '-' + String.fromCharCode(0x200f)
    + String.fromCharCode(0x2028) + '-' + String.fromCharCode(0x202e) + String.fromCharCode(0x2060) + '-'
    + String.fromCharCode(0x2064) + String.fromCharCode(0xfeff) + ']', 'g');
  const norm = (s) => s.normalize('NFKC').replace(ZERO_WIDTH, '').toLowerCase().replace(/\s+/g, ' ').trim();
  const cleanText = (s) => (s || '').replace(/\s+/g, ' ').replace(/^\+\d+ /, '').trim();

  // ------------------------------------------------------------------ grading queue
  const pending = new Map();   // norm text -> { text, entries: [] }
  let flushTimer = null;
  let backoffUntil = 0;

  function enqueue(entry) {
    const key = norm(entry.text);
    if (!key) return;
    const hit = cache.get(key);
    if (hit) { stats.cached++; settle(entry, hit); return; }
    let slot = pending.get(key);
    if (!slot) { slot = { text: entry.text, entries: [] }; pending.set(key, slot); }
    slot.entries.push(entry);
    if (pending.size >= 24) flush();
    else if (!flushTimer) flushTimer = setTimeout(flush, entry.kind === 'danmaku' ? 300 : 600);
  }

  async function flush() {
    clearTimeout(flushTimer); flushTimer = null;
    if (!pending.size || Date.now() < backoffUntil) { if (pending.size) flushTimer = setTimeout(flush, 2000); return; }
    const batch = Array.from(pending.entries()).slice(0, 40);
    for (const [k] of batch) pending.delete(k);
    const items = batch.map(([k, slot], i) => ({ id: String(i), text: slot.text }));
    try {
      const res = await post('/v1/grade', { items });
      const byId = new Map(res.results.map((v) => [v.id, v]));
      batch.forEach(([k, slot], i) => {
        const v = byId.get(String(i));
        if (!v) return;
        cache.set(k, v); cacheDirty = true;
        for (const e of slot.entries) settle(e, v);
      });
      setDot(false);
    } catch (err) {
      console.warn('[tonedown] grade failed:', err.message);
      backoffUntil = Date.now() + 10000;
      setDot(true);
    }
    if (pending.size) flushTimer = setTimeout(flush, 500);
  }

  function post(path, body) {
    return new Promise((resolve, reject) => {
      const headers = { 'Content-Type': 'application/json' };
      if (cfg.apiKey) headers['X-API-Key'] = cfg.apiKey;
      GM_xmlhttpRequest({
        method: 'POST', url: cfg.server.replace(/\/$/, '') + path, headers, data: JSON.stringify(body), timeout: 15000,
        onload: (r) => (r.status < 300 ? resolve(JSON.parse(r.responseText)) : reject(new Error('HTTP ' + r.status + ' ' + r.responseText.slice(0, 200)))),
        onerror: () => reject(new Error('network error')), ontimeout: () => reject(new Error('timeout')),
      });
    });
  }

  // ------------------------------------------------------------------ per-node state
  // Players reuse DOM elements for new danmaku, so a verdict belongs to (node, text), never to the node alone.
  const state = new WeakMap();   // node -> { text, verdict, entry, action }
  const tracked = new Set();     // nodes that currently carry a verdict, for re-applying when settings change

  function settle(entry, verdict) {
    stats.graded++;
    if (entry.onVerdict) { entry.onVerdict(verdict); return; }
    const st = state.get(entry.node);
    if (!st || st.text !== entry.text) return;   // the element moved on to another text while we were grading
    st.verdict = verdict;
    tracked.add(entry.node);
    apply(st);
    renderStats();
  }

  function forget(node) {
    const st = state.get(node);
    if (st) clearMarks(st.entry);
    state.delete(node);
    tracked.delete(node);
  }

  // ------------------------------------------------------------------ decisions
  const CRITICAL = ['self_harm', 'violence'];
  function topCategory(v) {
    const cats = v.categories || {};
    const present = Object.keys(cats).filter((k) => cats[k] >= 0.5).sort((x, y) => cats[y] - cats[x]);
    const critical = present.filter((k) => CRITICAL.includes(k));
    return critical.length ? critical[0] : (present[0] || null);
  }
  function decide(v) {
    if (!cfg.enabled) return 'show';
    const lvl = v.level_argmax;
    const top = topCategory(v);
    if (top && cfg.allow[top] && lvl < 4) return 'show';
    if (cfg.hideLevel <= 4 && lvl >= cfg.hideLevel) return 'hide';
    if (cfg.blur && cfg.hideLevel <= 4 && lvl >= 1 && lvl === cfg.hideLevel - 1) return 'blur';
    return 'show';
  }

  // Hiding is done with data attributes plus injected !important rules, because the Bilibili player
  // rewrites the inline style of every danmaku element it reuses.
  const RULES = '[data-tonedown-hide="v"]{visibility:hidden !important}'
    + '[data-tonedown-hide="d"]{display:none !important}'
    + '[data-tonedown-blur="1"]{filter:blur(5px) !important;opacity:.65 !important}';
  const styledRoots = new WeakSet();
  function ensureStyles(root) {
    if (!root || styledRoots.has(root)) return;
    styledRoots.add(root);
    const el = document.createElement('style');
    el.className = 'tonedown-rules';
    el.textContent = RULES;
    (root === document ? document.head : root).appendChild(el);
  }

  function apply(st) {
    const entry = st.entry;
    const box = entry.container;
    const body = entry.labelHost || box;
    if (!box || !box.isConnected) return;
    const action = decide(st.verdict);
    clearMarks(entry);
    st.action = action;
    box.dataset.tonedownLevel = String(st.verdict.level_argmax);
    if (action === 'hide') {
      ensureStyles(box.getRootNode());
      box.setAttribute('data-tonedown-hide', entry.kind === 'danmaku' ? 'v' : 'd');
    } else if (action === 'blur') {
      ensureStyles(body.getRootNode());
      body.setAttribute('data-tonedown-blur', '1');
      if (entry.kind !== 'danmaku') addChip(body, st.verdict);
    }
  }

  function clearMarks(entry) {
    const box = entry.container;
    const body = entry.labelHost || box;
    if (box) { box.removeAttribute('data-tonedown-hide'); delete box.dataset.tonedownLevel; }
    if (body) { body.removeAttribute('data-tonedown-blur'); removeChip(body); }
  }

  function addChip(body, verdict) {
    const chip = document.createElement('button');
    chip.className = 'tonedown-chip';
    const cat = topCategory(verdict);
    chip.textContent = `${T.folded}: ${cat ? CAT[cat] + ' · ' : ''}${LEVEL[verdict.level_argmax]} · ${T.reveal}`;
    chip.style.cssText = `all:unset;cursor:pointer;display:inline-block;margin:2px 0;padding:1px 8px;border-radius:10px;font-size:12px;color:#fff;background:${LEVEL_COLOR[verdict.level_argmax]};`;
    chip.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); body.removeAttribute('data-tonedown-blur'); chip.remove(); });
    body.parentNode && body.parentNode.insertBefore(chip, body);
  }
  function removeChip(body) {
    const prev = body.previousSibling;
    if (prev && prev.classList && prev.classList.contains('tonedown-chip')) prev.remove();
  }

  function reapplyAll() {
    for (const node of Array.from(tracked)) {
      const st = state.get(node);
      if (!st || !node.isConnected) { forget(node); continue; }
      apply(st);
    }
    renderStats();
  }

  // ------------------------------------------------------------------ adapters
  // Each adapter sweeps the page and returns {node, container, labelHost, text}. `node` is the element whose
  // text is watched; when its text changes it is judged again.
  function deepQueryAll(root, selector, out = []) {
    if (!root || !root.querySelectorAll) return out;
    root.querySelectorAll(selector).forEach((n) => out.push(n));
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) if (n.shadowRoot) deepQueryAll(n.shadowRoot, selector, out);
    return out;
  }
  const host = location.hostname;
  const adapters = [
    {
      name: 'bilibili-comments', kind: 'comment', active: () => host.endsWith('bilibili.com'),
      sweep() {
        const out = [];
        for (const comments of document.querySelectorAll('bili-comments')) {
          for (const rt of deepQueryAll(comments.shadowRoot, 'bili-rich-text')) {
            const contents = rt.shadowRoot ? rt.shadowRoot.querySelector('#contents') : null;
            const container = rt.getRootNode().host || rt;
            out.push({ node: rt, container, labelHost: contents || rt, text: cleanText((contents || rt).textContent) });
          }
        }
        for (const el of document.querySelectorAll('.reply-item .reply-content')) {
          out.push({ node: el, container: el.closest('.reply-item') || el, labelHost: el, text: cleanText(el.textContent) });
        }
        return out;
      },
    },
    {
      name: 'bilibili-danmaku', kind: 'danmaku', active: () => host === 'www.bilibili.com',
      hot: '.bpx-player-row-dm-wrap, .bilibili-player-video-danmaku',
      sweep() {
        const out = [];
        for (const el of document.querySelectorAll('.bili-danmaku-x-dm, .b-danmaku, .bili-dm')) {
          out.push({ node: el, container: el, labelHost: null, text: cleanText(el.textContent) });
        }
        return out;
      },
    },
    {
      name: 'bilibili-livechat', kind: 'danmaku', active: () => host === 'live.bilibili.com',
      hot: '#chat-items, .chat-items',
      sweep() {
        const out = [];
        for (const el of document.querySelectorAll('.chat-item.danmaku-item')) {
          const body = el.querySelector('.danmaku-item-right');
          out.push({ node: el, container: el, labelHost: body, text: cleanText(el.dataset.danmaku || (body || el).textContent) });
        }
        return out;
      },
    },
    {
      name: 'youtube-comments', kind: 'comment', active: () => host.endsWith('youtube.com') && !location.pathname.startsWith('/live_chat'),
      sweep() {
        const out = [];
        for (const el of document.querySelectorAll('ytd-comment-view-model, ytd-comment-renderer')) {
          const body = el.querySelector('#content-text');
          if (body) out.push({ node: el, container: el, labelHost: body, text: cleanText(body.innerText) });
        }
        return out;
      },
    },
    {
      name: 'youtube-livechat', kind: 'danmaku', active: () => host.endsWith('youtube.com') && location.pathname.startsWith('/live_chat'),
      hot: '#items.yt-live-chat-item-list-renderer',
      sweep() {
        const out = [];
        for (const el of document.querySelectorAll('yt-live-chat-text-message-renderer, yt-live-chat-paid-message-renderer')) {
          const body = el.querySelector('#message');
          if (body) out.push({ node: el, container: el, labelHost: body, text: cleanText(body.innerText) });
        }
        return out;
      },
    },
  ].filter((a) => a.active());

  function sweepAll() {
    if (!cfg.enabled) return;
    for (const a of adapters) {
      let found;
      try { found = a.sweep(); } catch (err) { console.warn('[tonedown] adapter', a.name, err); continue; }
      for (const c of found) {
        const st = state.get(c.node);
        if (!c.text || c.text.length < 2) { if (st) forget(c.node); continue; }
        if (st && st.text === c.text) continue;          // same text as last time: nothing to do
        if (st) forget(c.node);                            // reused element: undo the old verdict right away
        const entry = Object.assign(c, { kind: a.kind, adapter: a.name });
        state.set(c.node, { text: c.text, verdict: null, entry, action: 'show' });
        enqueue(entry);
      }
    }
  }
  let sweepTimer = null, sweepDue = 0;
  function scheduleSweep(ms) {
    const due = Date.now() + ms;
    if (sweepTimer && sweepDue <= due) return;
    clearTimeout(sweepTimer);
    sweepDue = due;
    sweepTimer = setTimeout(() => { sweepTimer = null; sweepAll(); }, ms);
  }
  new MutationObserver(() => scheduleSweep(400)).observe(document.documentElement, { childList: true, subtree: true });
  setInterval(sweepAll, 1500);
  setInterval(() => { for (const node of Array.from(tracked)) if (!node.isConnected) forget(node); }, 30000);
  // Danmaku live for a few seconds and their elements are recycled, so watch the container itself, text included.
  setInterval(() => {
    for (const a of adapters) {
      if (!a.hot || a.hotObserved) continue;
      const el = document.querySelector(a.hot);
      if (!el) continue;
      a.hotObserved = true;
      new MutationObserver(() => scheduleSweep(50)).observe(el, { childList: true, subtree: true, characterData: true });
    }
  }, 2000);
  sweepAll();

  // ------------------------------------------------------------------ composer self-check
  const drafts = new WeakMap();
  document.addEventListener('input', (ev) => {
    if (!cfg.composer || !cfg.enabled) return;
    const el = (ev.composedPath && ev.composedPath()[0]) || ev.target;
    if (!el || !(el.matches && el.matches('textarea, [contenteditable="true"], [contenteditable=""]'))) return;
    clearTimeout(drafts.get(el));
    drafts.set(el, setTimeout(() => checkDraft(el), 1200));
  }, true);

  function checkDraft(el) {
    const text = ('value' in el ? el.value : el.innerText || '').trim();
    let hint = el.parentNode && el.parentNode.querySelector(':scope > .tonedown-draft');
    if (text.length < 3) { if (hint) hint.remove(); return; }
    enqueue({ text, kind: 'draft', container: el, onVerdict: (v) => {
      const now = ('value' in el ? el.value : el.innerText || '').trim();
      if (now !== text) return;
      if (!hint) { hint = document.createElement('div'); hint.className = 'tonedown-draft'; el.parentNode && el.parentNode.insertBefore(hint, el.nextSibling); }
      const lvl = v.level_argmax, cat = topCategory(v);
      hint.style.cssText = `font-size:12px;margin-top:4px;padding:2px 8px;border-radius:8px;color:#fff;display:inline-block;background:${LEVEL_COLOR[lvl]}`;
      hint.textContent = `${T.draft}: ${LEVEL[lvl]}${cat ? ' · ' + CAT[cat] : ''}${lvl >= 2 ? ' · ' + T.draftHint : ''}`;
      if (lvl === 0) setTimeout(() => hint && hint.remove(), 4000);
    } });
  }

  // ------------------------------------------------------------------ panel
  let panel, button, dot, statsEl, statsTimer = null;
  function setDot(bad) { if (dot) dot.style.background = bad ? '#d32f2f' : '#2e7d32'; }
  function renderStats() {
    if (!statsEl || statsTimer) return;
    statsTimer = setTimeout(() => {
      statsTimer = null;
      let hidden = 0, blurred = 0;
      for (const node of tracked) {
        const st = state.get(node);
        if (!st) continue;
        if (st.action === 'hide') hidden++; else if (st.action === 'blur') blurred++;
      }
      statsEl.textContent = T.stats({ graded: stats.graded, cached: stats.cached, hidden, blurred });
    }, 300);
  }
  function buildPanel() {
    if (!isTop || panel) return;
    const css = document.createElement('style');
    css.textContent = `
      .tonedown-btn{position:fixed;right:16px;bottom:16px;z-index:2147483646;width:40px;height:40px;border-radius:20px;border:none;background:#1f2937;color:#fff;font:600 12px system-ui;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.3)}
      .tonedown-dot{position:absolute;top:4px;right:4px;width:8px;height:8px;border-radius:4px;background:#2e7d32}
      .tonedown-panel{position:fixed;right:16px;bottom:64px;z-index:2147483646;width:300px;padding:12px 14px;border-radius:12px;background:#fff;color:#111;font:13px/1.5 system-ui;box-shadow:0 4px 24px rgba(0,0,0,.25)}
      .tonedown-panel h3{margin:0 0 8px;font-size:14px}
      .tonedown-panel label{display:block;margin:4px 0}
      .tonedown-panel input[type=text]{width:100%;box-sizing:border-box;padding:4px 6px;border:1px solid #ccc;border-radius:6px;font-size:12px}
      .tonedown-panel input[type=range]{width:100%}
      .tonedown-panel .tonedown-cats label{display:inline-block;margin:2px 8px 2px 0}
      .tonedown-panel .tonedown-row{display:flex;gap:6px;align-items:center}
      .tonedown-panel button{padding:3px 10px;border-radius:6px;border:1px solid #999;background:#f5f5f5;cursor:pointer;font-size:12px}
      .tonedown-panel small{color:#666}
      @media (prefers-color-scheme: dark){.tonedown-panel{background:#1f2937;color:#eee}.tonedown-panel input[type=text]{background:#111;color:#eee;border-color:#555}.tonedown-panel button{background:#374151;color:#eee;border-color:#555}.tonedown-panel small{color:#aaa}}`;
    document.head.appendChild(css);
    button = document.createElement('button'); button.className = 'tonedown-btn'; button.textContent = 'TD'; button.title = T.title;
    dot = document.createElement('span'); dot.className = 'tonedown-dot'; button.appendChild(dot);
    button.addEventListener('click', () => { panel.hidden = !panel.hidden; });
    panel = document.createElement('div'); panel.className = 'tonedown-panel'; panel.hidden = true;
    const cats = Object.keys(CAT).map((k) => `<label><input type="checkbox" data-cat="${k}" ${cfg.allow[k] ? 'checked' : ''}> ${CAT[k]}</label>`).join('');
    panel.innerHTML = `
      <h3>${T.title}</h3>
      <label><input type="checkbox" id="tonedown-enabled" ${cfg.enabled ? 'checked' : ''}> ${T.enabled}</label>
      <label><input type="range" id="tonedown-level" min="1" max="5" value="${cfg.hideLevel}"><span id="tonedown-level-text"></span></label>
      <label><input type="checkbox" id="tonedown-blur" ${cfg.blur ? 'checked' : ''}> ${T.blur}</label>
      <label><input type="checkbox" id="tonedown-composer" ${cfg.composer ? 'checked' : ''}> ${T.composer}</label>
      <div><small>${T.allow}</small><div class="tonedown-cats">${cats}</div></div>
      <label>${T.server}<input type="text" id="tonedown-server" value="${escapeHtml(cfg.server)}"></label>
      <label>${T.key}<input type="text" id="tonedown-key" value="${escapeHtml(cfg.apiKey)}"></label>
      <div class="tonedown-row"><button id="tonedown-test">${T.test}</button><small id="tonedown-test-out"></small></div>
      <small id="tonedown-stats"></small>`;
    document.body.appendChild(button); document.body.appendChild(panel);
    statsEl = panel.querySelector('#tonedown-stats'); renderStats();
    const levelText = panel.querySelector('#tonedown-level-text');
    const showLevel = () => { levelText.textContent = ' ' + T.slider[cfg.hideLevel - 1]; };
    showLevel();
    panel.querySelector('#tonedown-level').addEventListener('input', (e) => { cfg.hideLevel = Number(e.target.value); showLevel(); saveCfg(); reapplyAll(); });
    panel.querySelector('#tonedown-enabled').addEventListener('change', (e) => { cfg.enabled = e.target.checked; saveCfg(); reapplyAll(); if (cfg.enabled) sweepAll(); });
    panel.querySelector('#tonedown-blur').addEventListener('change', (e) => { cfg.blur = e.target.checked; saveCfg(); reapplyAll(); });
    panel.querySelector('#tonedown-composer').addEventListener('change', (e) => { cfg.composer = e.target.checked; saveCfg(); });
    panel.querySelectorAll('[data-cat]').forEach((cb) => cb.addEventListener('change', (e) => { cfg.allow[e.target.dataset.cat] = e.target.checked; saveCfg(); reapplyAll(); }));
    panel.querySelector('#tonedown-server').addEventListener('change', (e) => { cfg.server = e.target.value.trim(); saveCfg(); });
    panel.querySelector('#tonedown-key').addEventListener('change', (e) => { cfg.apiKey = e.target.value.trim(); saveCfg(); });
    panel.querySelector('#tonedown-test').addEventListener('click', () => {
      const out = panel.querySelector('#tonedown-test-out'); out.textContent = '...';
      GM_xmlhttpRequest({ method: 'GET', url: cfg.server.replace(/\/$/, '') + '/healthz', timeout: 8000,
        onload: (r) => { out.textContent = r.status < 300 ? `${T.ok} (${safeParse(r.responseText, {}).backend || '?'})` : `${T.fail} HTTP ${r.status}`; setDot(r.status >= 300); },
        onerror: () => { out.textContent = T.fail; setDot(true); }, ontimeout: () => { out.textContent = T.fail; setDot(true); } });
    });
  }
  if (isTop) {
    buildPanel();
    GM_registerMenuCommand(T.title, () => { panel.hidden = !panel.hidden; });
  }

  // ------------------------------------------------------------------ utils
  function safeParse(s, fallback) { try { return JSON.parse(s); } catch (e) { return fallback; } }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
})();
