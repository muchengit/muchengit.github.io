/* ==========================================================================
   blog.js — 文章页增强：阅读进度 / 目录 / 元信息条 / 代码复制 / 上下篇 / 回到顶部
   与页面内联脚本不冲突：这里不注册语言切换按钮事件。
   ========================================================================== */
(function () {
  'use strict';

  var ARTICLES = window.SITE_ARTICLES || [];
  var article = document.querySelector('article');
  if (!article) return;

  /* ---------- 当前文章 ---------- */
  var file = (location.pathname.split('/').pop() || '').toLowerCase();
  var idx = -1;
  for (var i = 0; i < ARTICLES.length; i++) {
    if (ARTICLES[i].file.toLowerCase() === file) { idx = i; break; }
  }
  var current = idx >= 0 ? ARTICLES[idx] : null;

  /* ---------- 阅读时长 & 字数 ---------- */
  function countWords() {
    var text = article.innerText || '';
    var cjk = (text.match(/[\u4e00-\u9fa5\u3040-\u30ff]/g) || []).length;
    var words = (text.match(/[A-Za-z0-9]+/g) || []).length;
    return { cjk: cjk, words: words, minutes: Math.max(1, Math.round(cjk / 400 + words / 200)) };
  }

  /* ======================================================================
     1. 阅读进度条
     ====================================================================== */
  var bar = document.createElement('div');
  bar.className = 'read-progress';
  document.body.appendChild(bar);

  /* ======================================================================
     2. 回到顶部
     ====================================================================== */
  var toTop = document.createElement('button');
  toTop.className = 'to-top';
  toTop.type = 'button';
  toTop.setAttribute('aria-label', 'Back to top');
  toTop.innerHTML = '&uarr;';
  document.body.appendChild(toTop);

  /* ======================================================================
     3. 元信息条（分类 / 日期 / 阅读时长）
     ====================================================================== */
  var header = article.querySelector('header');
  if (current) {
    var wc = countWords();
    var meta = document.createElement('div');
    meta.className = 'art-meta';
    meta.innerHTML =
      '<span class="m"><b>' + esc(current.cat) + '</b></span><span class="sep"></span>' +
      '<span class="m">' + current.date + '</span><span class="sep"></span>' +
      '<span class="m">约 <b>' + wc.minutes + '</b> 分钟读完</span><span class="sep"></span>' +
      '<span class="m">' + (wc.cjk + wc.words).toLocaleString() + ' 字</span>';
    (header || article).insertAdjacentElement('afterend', meta);
  }

  /* ======================================================================
     4. 目录（TOC）
     ====================================================================== */
  var headings = Array.prototype.slice.call(article.querySelectorAll('.prose h2'));
  if (headings.length >= 2) {
    var toc = document.createElement('details');
    toc.className = 'toc';
    toc.open = true;

    var sum = document.createElement('summary');
    sum.innerHTML = '目录 / Contents <span class="toc-arrow">&rsaquo;</span>';
    toc.appendChild(sum);

    var list = document.createElement('ul');
    list.className = 'toc-list';
    var links = [];
    headings.forEach(function (h, n) {
      if (!h.id) h.id = 'sec-' + (n + 1);
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + h.id;
      /* innerText 会跳过 display:none 的另一种语言，只取当前可见文案 */
      var label = (h.innerText || h.textContent || '').trim().replace(/^(目录|Contents)\s*/i, '');
      a.textContent = label;
      li.appendChild(a);
      list.appendChild(li);
      links.push({ el: a, target: h });
    });
    toc.appendChild(list);

    var anchor = document.querySelector('.art-meta');
    if (anchor) anchor.insertAdjacentElement('afterend', toc);
    else (header || article).insertAdjacentElement('afterend', toc);

    /* 目录高亮（滚动联动） */
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (l) { l.el.classList.toggle('active', l.target === e.target); });
      });
    }, { rootMargin: '-100px 0px -65% 0px', threshold: 0 });
    headings.forEach(function (h) { spy.observe(h); });
  }

  /* ======================================================================
     5. 代码复制按钮
     ====================================================================== */
  Array.prototype.forEach.call(article.querySelectorAll('pre'), function (pre) {
    var btn = document.createElement('button');
    btn.className = 'code-copy';
    btn.type = 'button';
    btn.textContent = 'COPY';
    btn.setAttribute('aria-label', 'Copy code');
    pre.appendChild(btn);
    btn.addEventListener('click', function () {
      var code = pre.querySelector('code');
      var text = code ? code.innerText : pre.innerText;
      var done = function () {
        btn.textContent = 'COPIED';
        btn.classList.add('done');
        setTimeout(function () { btn.textContent = 'COPY'; btn.classList.remove('done'); }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(function () { fallback(text, done); });
      } else {
        fallback(text, done);
      }
    });
  });

  function fallback(text, cb) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); cb(); } catch (e) { /* ignore */ }
    document.body.removeChild(ta);
  }

  /* ======================================================================
     6. 上下篇导航
     ====================================================================== */
  if (idx >= 0 && ARTICLES.length > 1) {
    var newer = ARTICLES[idx - 1] || null;   // 更新的一篇
    var older = ARTICLES[idx + 1] || null;   // 更早的一篇
    var nav = document.createElement('nav');
    nav.className = 'pn-nav';
    nav.setAttribute('aria-label', 'Article navigation');
    nav.innerHTML =
      pnItem(newer, '← 更新的一篇 / Newer', 'prev') +
      pnItem(older, '更早的一篇 / Older →', 'next');
    var foot = document.querySelector('.foot-link');
    if (foot) foot.parentNode.insertBefore(nav, foot);
    else article.insertAdjacentElement('afterend', nav);
  }

  function pnItem(a, label, cls) {
    if (!a) return '<div class="empty ' + cls + '"><span class="dir">' + label + '</span></div>';
    return '<a class="' + cls + '" href="' + a.file + '">' +
      '<span class="dir">' + label + '</span>' +
      '<span class="t">' + esc(a.zh) + '</span></a>';
  }

  /* ======================================================================
     7. 外链新窗口打开
     ====================================================================== */
  Array.prototype.forEach.call(article.querySelectorAll('a[href^="http"]'), function (a) {
    if (a.host && a.host !== location.host) {
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
    }
  });

  /* ======================================================================
     8. 滚动监听（进度条 / 回到顶部 / 导航态）
     ====================================================================== */
  var navIn = document.querySelector('.nav-in');
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      var pct = h > 0 ? (window.scrollY / h) * 100 : 0;
      bar.style.width = Math.min(100, Math.max(0, pct)) + '%';
      toTop.classList.toggle('show', window.scrollY > 600);
      if (navIn) navIn.classList.toggle('scrolled', window.scrollY > 10);
      ticking = false;
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  onScroll();

  toTop.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
})();
