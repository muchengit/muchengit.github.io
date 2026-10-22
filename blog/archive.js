/* ==========================================================================
   archive.js — 归档页逻辑：年份 / 分类 / 标签筛选 + 实时搜索 + URL 同步
   （静态 HTML 已包含全部文章，JS 只负责显示 / 隐藏，不负责生成内容）
   依赖：articles.js（SITE_ARTICLES）、blog.js
   URL 形式：index.html?cat=AI%20编程&tag=AI%20调试&q=prompt#2026
             index.html#cat=AI%20编程&tag=AI%20调试&q=prompt
   ========================================================================== */
(function () {
  'use strict';

  var ARTICLES = window.SITE_ARTICLES || [];
  var list = document.getElementById('postList');
  if (!list) return;

  var posts = Array.prototype.slice.call(list.querySelectorAll('.post'));
  var groups = Array.prototype.slice.call(list.querySelectorAll('.ygroup'));
  var yearPills = document.getElementById('yearPills');
  var catPills = document.getElementById('catPills');
  var input = document.getElementById('q');
  var cnt = document.getElementById('cnt');
  var cntEn = document.getElementById('cnt-en');
  var tot = document.getElementById('tot');
  var totEn = document.getElementById('tot-en');
  var empty = document.getElementById('empty');
  var state = { year: '', cat: '', tag: '', q: '' };

  /* ---------- 1. 统计信息（来自 articles.js，words 字段为各篇正文实际字数） ---------- */
  function countBodyWords() {
    var sum = 0;
    ARTICLES.forEach(function (a) { sum += (parseInt(a.words, 10) || 0); });
    return sum;
  }
  if (ARTICLES.length) {
    var latest = ARTICLES.reduce(function (acc, a) {
      return (!acc || String(a.date) > String(acc)) ? a.date : acc;
    }, '');
    var setNum = function (id, v) { var el = document.getElementById(id); if (el) el.textContent = v; };
    var bodyWords = countBodyWords();
    setNum('statCount', ARTICLES.length);
    setNum('statWords', bodyWords.toLocaleString());
    setNum('statRead', Math.max(1, Math.round(bodyWords / 400)));
    setNum('statLatest', latest);
    setNum('tot', ARTICLES.length);
    setNum('tot-en', ARTICLES.length);
  }

  /* ---------- 2. 分类按钮：按 articles.js 动态生成 ---------- */
  if (catPills && ARTICLES.length) {
    var seen = {}, order = [];
    ARTICLES.forEach(function (a) {
      if (!a.cat || seen[a.cat]) return;
      seen[a.cat] = 1; order.push(a);
    });
    catPills.innerHTML = '';
    var all = document.createElement('button');
    all.type = 'button';
    all.className = 'pill active';
    all.setAttribute('data-cat', '');
    all.innerHTML = '<span class="zh-only">全部</span><span class="en-only">All</span>';
    catPills.appendChild(all);
    order.forEach(function (a) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'pill';
      b.setAttribute('data-cat', a.cat);
      b.setAttribute('data-cat-en', a.catEn || '');
      b.innerHTML = '<span class="zh-only">' + esc(a.cat) + '</span><span class="en-only">' + esc(a.catEn || '') + '</span>';
      catPills.appendChild(b);
    });
  }

  /* ---------- 3. 筛选 / 搜索 ---------- */
  function matchCat(post, cat) {
    if (!cat) return true;
    var c = (post.getAttribute('data-cat') || '').toLowerCase();
    var e = (post.getAttribute('data-cat-en') || '').toLowerCase();
    var want = cat.toLowerCase();
    return c === want || e === want;
  }

  function matchTag(post, tag) {
    if (!tag) return true;
    var raw = post.getAttribute('data-tags') || '';
    if (!raw) return false;
    var want = tag.toLowerCase();
    return raw.split('|').some(function (t) { return t.toLowerCase() === want; });
  }

  function apply() {
    var term = (state.q || '').trim().toLowerCase();
    var shown = 0;
    posts.forEach(function (p) {
      var ok = true;
      if (state.year && p.getAttribute('data-year') !== state.year) ok = false;
      if (ok && !matchCat(p, state.cat)) ok = false;
      if (ok && !matchTag(p, state.tag)) ok = false;
      if (ok && term) {
        var hay = (p.textContent || '') + ' ' + (p.getAttribute('data-year') || '') +
                  ' ' + (p.getAttribute('data-tags') || '');
        if (hay.toLowerCase().indexOf(term) === -1) ok = false;
      }
      p.classList.toggle('hidden', !ok);
      if (ok) shown++;
    });
    groups.forEach(function (g) {
      var n = g.querySelectorAll('.post:not(.hidden)').length;
      g.classList.toggle('hidden', n === 0);
      Array.prototype.forEach.call(g.querySelectorAll('.yn-count'), function (b) { b.textContent = n; });
    });
    if (cnt) cnt.textContent = shown;
    if (cntEn) cntEn.textContent = shown;
    if (empty) empty.classList.toggle('show', shown === 0);

    var chip = document.getElementById('tagChip');
    if (chip) {
      if (state.tag) {
        chip.style.display = '';
        var lbl = chip.querySelector('.zh-only');
        var lblEn = chip.querySelector('.en-only');
        if (lbl) lbl.textContent = '标签：' + state.tag;
        if (lblEn) lblEn.textContent = 'Tag: ' + state.tag;
      } else {
        chip.style.display = 'none';
      }
    }
  }

  /* ---------- 4. URL 同步（?cat=入门&tag=AI 调试&q=prompt #2026） ---------- */
  function parseQuery(str) {
    var st = { year: '', cat: '', tag: '', q: '' };
    if (!str) return st;
    str.replace(/^[#?]/, '').split('&').forEach(function (part) {
      if (!part) return;
      var i = part.indexOf('=');
      var k = i < 0 ? part : part.slice(0, i);
      var v = i < 0 ? '' : part.slice(i + 1);
      try { k = decodeURIComponent(k); v = decodeURIComponent(v); } catch (e) {}
      k = String(k).trim(); v = String(v).trim();
      if (k === 'cat') st.cat = v;
      else if (k === 'tag') st.tag = v;
      else if (k === 'q') st.q = v;
      else if (k === 'year') st.year = v;
      else if (/^\d{4}$/.test(k)) st.year = k;
    });
    return st;
  }

  function readState() {
    var st = parseQuery(location.search);
    var h = parseQuery(location.hash);
    if (h.year) st.year = h.year;
    if (h.cat) st.cat = h.cat;
    if (h.tag) st.tag = h.tag;
    if (h.q) st.q = h.q;
    return st;
  }

  function writeState() {
    var parts = [];
    if (state.year) parts.push('year=' + encodeURIComponent(state.year));
    if (state.cat) parts.push('cat=' + encodeURIComponent(state.cat));
    if (state.tag) parts.push('tag=' + encodeURIComponent(state.tag));
    if (state.q) parts.push('q=' + encodeURIComponent(state.q));
    var qs = parts.length ? ('?' + parts.join('&')) : '';
    var hash = state.year ? ('#' + encodeURIComponent(state.year)) : '';
    try {
      history.replaceState(null, '', location.pathname + qs + hash);
    } catch (e) {
      /* 老浏览器降级 */
    }
  }

  function syncUI() {
    Array.prototype.forEach.call(yearPills ? yearPills.querySelectorAll('.pill') : [], function (b) {
      b.classList.toggle('active', (b.getAttribute('data-year') || '') === state.year);
    });
    Array.prototype.forEach.call(catPills ? catPills.querySelectorAll('.pill') : [], function (b) {
      var v = b.getAttribute('data-cat') || '';
      b.classList.toggle('active', v === state.cat);
    });
    if (input && input.value !== state.q) input.value = state.q;
  }

  function setState(patch) {
    state.year = patch.year || '';
    state.cat = patch.cat || '';
    state.tag = patch.tag || '';
    state.q = patch.q || '';
    syncUI();
    apply();
    writeState();
  }

  if (yearPills) yearPills.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.pill') : null;
    if (!b) return;
    setState({ year: b.getAttribute('data-year') || '', cat: state.cat, tag: state.tag, q: state.q });
  });
  if (catPills) catPills.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.pill') : null;
    if (!b) return;
    setState({ year: state.year, cat: b.getAttribute('data-cat') || '', tag: state.tag, q: state.q });
  });
  if (input) input.addEventListener('input', function () {
    setState({ year: state.year, cat: state.cat, tag: state.tag, q: input.value });
  });

  function clearAll() {
    setState({ year: '', cat: '', tag: '', q: '' });
  }
  var clearBtn = document.getElementById('clearBtn');
  if (clearBtn) clearBtn.addEventListener('click', clearAll);
  var emptyClear = document.getElementById('emptyClear');
  if (emptyClear) emptyClear.addEventListener('click', clearAll);
  var tagClear = document.getElementById('tagClear');
  if (tagClear) tagClear.addEventListener('click', function () {
    setState({ year: state.year, cat: state.cat, tag: '', q: state.q });
  });

  window.addEventListener('hashchange', function () {
    state = readState();
    syncUI();
    apply();
  });

  /* ---------- 5. 搜索框占位符跟随语言切换 ---------- */
  function syncPlaceholder() {
    if (!input) return;
    var lang = document.body.getAttribute('data-lang') || 'zh';
    input.placeholder = lang === 'zh'
      ? (input.getAttribute('data-ph-zh') || '')
      : (input.getAttribute('data-ph-en') || '');
  }
  syncPlaceholder();
  if (window.MutationObserver) {
    new MutationObserver(syncPlaceholder).observe(document.body, { attributes: true, attributeFilter: ['data-lang'] });
  }

  /* ---------- 6. 移动端菜单（与主页 index.html 一致） ---------- */
  var menuBtn = document.getElementById('menubtn');
  var navLinks = document.getElementById('navlinks');
  if (menuBtn && navLinks) {
    menuBtn.addEventListener('click', function () { navLinks.classList.toggle('open'); });
    Array.prototype.forEach.call(navLinks.querySelectorAll('a'), function (a) {
      a.addEventListener('click', function () { navLinks.classList.remove('open'); });
    });
  }

  /* ---------- 7. 初始化：还原 URL 状态 ---------- */
  state = readState();
  syncUI();
  apply();

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
})();
