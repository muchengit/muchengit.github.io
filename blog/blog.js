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

/* ==========================================================================
   9. 右侧浮动工具栏 + 全文朗读（TTS）
   --------------------------------------------------------------------------
   追加块，不改动上面任何函数体与 CSS 规则。
   注意：这里不注册语言切换按钮的 click 事件 —— 语言切换由各页面内联脚本负责。
   ========================================================================== */
(function () {
  'use strict';

  var ARTICLES = window.SITE_ARTICLES || [];
  var article = document.querySelector('article');
  if (!article || !article.querySelector('.prose')) return;   // 只在真正的文章页启用工具栏

  var here = (location.pathname.split('/').pop() || '').toLowerCase();
  var self = null;
  for (var i = 0; i < ARTICLES.length; i++) {
    if (String(ARTICLES[i].file).toLowerCase() === here) { self = ARTICLES[i]; break; }
  }

  /* ---------- 小工具 ---------- */
  function lang() {
    return (document.body.getAttribute('data-lang') || 'zh').toLowerCase() === 'en' ? 'en' : 'zh';
  }
  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function copyText(text, ok, fail) {
    function legacy() {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      var done = false;
      try { done = document.execCommand('copy'); } catch (e) { done = false; }
      document.body.removeChild(ta);
      if (done) { if (ok) ok(); } else if (fail) fail();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { if (ok) ok(); }).catch(legacy);
    } else legacy();
  }

  /* ======================================================================
     9.1 朗读能力检测
     ====================================================================== */
  var synth = window.speechSynthesis;
  var ttsSupported = !!(synth && typeof window.SpeechSynthesisUtterance === 'function');

  var MSG = {
    ready:   { zh: '准备就绪', en: 'Ready' },
    playing: { zh: '朗读中', en: 'Reading' },
    paused:  { zh: '已暂停', en: 'Paused' },
    done:    { zh: '朗读结束', en: 'Finished' },
    error:   { zh: '语音不可用，请检查系统语音设置', en: 'Voice unavailable — check your system voice settings' },
    again:   { zh: '语言已切换，请重新开始朗读', en: 'Language changed — press play again' },
    empty:   { zh: '没有可朗读的正文', en: 'Nothing to read' }
  };
  function msg(key) {
    var m = MSG[key] || MSG.ready;
    return lang() === 'en' ? m.en : m.zh;
  }

  /* ======================================================================
     9.2 朗读面板
     ====================================================================== */
  var panel = document.createElement('div');
  panel.className = 'tts-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', '全文朗读 / Read aloud');
  panel.innerHTML =
    '<div class="tts-head">' +
      '<span class="tts-title"><span class="zh-only">全文朗读</span><span class="en-only">Read aloud</span></span>' +
      '<button class="tts-close" type="button" title="关闭 / Close" aria-label="关闭 / Close">✕</button>' +
    '</div>' +
    '<div class="tts-status"><span class="tts-state"></span><span class="tts-count"></span></div>' +
    '<div class="tts-bar"><i></i></div>' +
    '<div class="tts-ctrls">' +
      '<button class="tts-btn tts-play" type="button" data-act="play" title="播放 / Play" aria-label="播放 / Play">▶</button>' +
      '<button class="tts-btn tts-pause" type="button" data-act="pause" title="暂停 / Pause" aria-label="暂停 / Pause">❚❚</button>' +
      '<button class="tts-btn tts-stop" type="button" data-act="stop" title="停止 / Stop" aria-label="停止 / Stop">■</button>' +
    '</div>' +
    '<label class="tts-row"><span class="tts-k"><span class="zh-only">语速</span><span class="en-only">Rate</span></span>' +
      '<input class="tts-rate" type="range" min="0.7" max="1.6" step="0.1" value="1">' +
      '<span class="tts-val">1.0x</span></label>' +
    '<label class="tts-row tts-voice-row off"><span class="tts-k"><span class="zh-only">语音</span><span class="en-only">Voice</span></span>' +
      '<select class="tts-voice"></select></label>' +
    '<p class="tts-note"><span class="zh-only">按段落朗读，已跳过代码块与装饰元素；切换语言后请重新播放。</span>' +
      '<span class="en-only">Reads paragraph by paragraph. Code blocks and decorative elements are skipped; press play again after switching language.</span></p>';
  document.body.appendChild(panel);

  var elState = panel.querySelector('.tts-state');
  var elCount = panel.querySelector('.tts-count');
  var elBar = panel.querySelector('.tts-bar i');
  var elPlay = panel.querySelector('.tts-play');
  var elPause = panel.querySelector('.tts-pause');
  var elStop = panel.querySelector('.tts-stop');
  var elRate = panel.querySelector('.tts-rate');
  var elRateVal = panel.querySelector('.tts-val');
  var elVoiceRow = panel.querySelector('.tts-voice-row');
  var elVoice = panel.querySelector('.tts-voice');

  /* ---------- 语速 ---------- */
  var rate = 1;
  elRate.addEventListener('input', function () {
    rate = parseFloat(elRate.value) || 1;
    elRateVal.textContent = rate.toFixed(1) + 'x';
  });

  /* ---------- 语音列表 ---------- */
  var voices = [];
  var voiceURI = '';
  function loadVoices() {
    if (!synth || typeof synth.getVoices !== 'function') return;
    var v = synth.getVoices() || [];
    if (!v.length) return;
    voices = v;
    fillVoices();
  }
  function fillVoices() {
    if (!voices.length) { elVoiceRow.classList.add('off'); return; }
    var lg = lang();
    var list = [];
    for (var i = 0; i < voices.length; i++) {
      var l = String(voices[i].lang || '').toLowerCase();
      if (lg === 'en' ? l.indexOf('en') === 0 : l.indexOf('zh') === 0) list.push(voices[i]);
    }
    if (!list.length) { elVoiceRow.classList.add('off'); return; }
    elVoiceRow.classList.remove('off');
    elVoice.innerHTML = '';
    var auto = document.createElement('option');
    auto.value = '';
    auto.textContent = lg === 'en' ? 'Auto' : '自动';
    elVoice.appendChild(auto);
    for (var j = 0; j < list.length; j++) {
      var o = document.createElement('option');
      o.value = list[j].voiceURI;
      o.textContent = list[j].name + ' (' + list[j].lang + ')';
      elVoice.appendChild(o);
    }
    var keep = '';
    for (var k = 0; k < list.length; k++) if (list[k].voiceURI === voiceURI) keep = voiceURI;
    elVoice.value = keep;
    voiceURI = keep;
  }
  elVoice.addEventListener('change', function () { voiceURI = elVoice.value || ''; });
  if (synth && typeof synth.addEventListener === 'function') {
    synth.addEventListener('voiceschanged', loadVoices);
  }
  loadVoices();
  setTimeout(loadVoices, 500);
  setTimeout(loadVoices, 1800);

  function pickVoice() {
    var lg = lang(), i, l;
    if (voiceURI) {
      for (i = 0; i < voices.length; i++) if (voices[i].voiceURI === voiceURI) return voices[i];
    }
    for (i = 0; i < voices.length; i++) {
      l = String(voices[i].lang || '').toLowerCase();
      if (lg === 'en' ? l.indexOf('en') === 0 : l.indexOf('zh') === 0) return voices[i];
    }
    return null;
  }

  /* ======================================================================
     9.3 正文分段
     ====================================================================== */
  /* 取“当前语言下可见”的文本：克隆节点 → 移除另一种语言的 .zh-only/.en-only
     → 去掉代码块与装饰元素 → 取 textContent（不用 innerText，跨浏览器行为不一致） */
  function visibleText(el, lg) {
    var clone = el.cloneNode(true);
    var hide = lg === 'en' ? 'zh-only' : 'en-only';
    var nodes = clone.querySelectorAll('.' + hide);
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].parentNode) nodes[i].parentNode.removeChild(nodes[i]);
    }
    var junk = clone.querySelectorAll('pre, .code-copy, .toc, svg, button, iframe');
    for (var j = 0; j < junk.length; j++) {
      if (junk[j].parentNode) junk[j].parentNode.removeChild(junk[j]);
    }
    var cells = clone.querySelectorAll('td, th');
    for (var k = 0; k < cells.length; k++) {
      cells[k].appendChild(document.createTextNode(' | '));
    }
    return (clone.textContent || '').replace(/\s+/g, ' ').trim();
  }

  /* 长句切块：优先在句末标点断开，其次空格，再次逗号，最后硬切。
     Chrome 对过长 utterance 有截断问题，切块后朗读更稳。 */
  function splitText(text, max) {
    var out = [];
    var t = String(text || '').replace(/\s+/g, ' ').trim();
    if (!t) return out;
    while (t.length > max) {
      var cut = -1;
      var head = t.slice(0, max + 1);
      var m = head.match(/[。！？!?]\s*$/);
      if (m) cut = m.index + m[0].length;
      if (cut < 0) {
        var sp = head.lastIndexOf(' ');
        if (sp > max * 0.4) cut = sp + 1;
      }
      if (cut < 0) {
        var cm = head.match(/[,，、;；:：]\s*$/);
        cut = cm ? cm.index + cm[0].length : max;
      }
      if (cut < 1) cut = max;
      out.push(t.slice(0, cut).trim());
      t = t.slice(cut).trim();
    }
    if (t) out.push(t);
    return out;
  }

  var MAX_CHUNK = 140;
  function buildSegments() {
    var lg = lang();
    var list = [];
    var sections = article.querySelectorAll('.prose');
    for (var i = 0; i < sections.length; i++) {
      var kids = sections[i].children;
      for (var j = 0; j < kids.length; j++) {
        var el = kids[j];
        var tag = String(el.tagName || '').toLowerCase();
        if (tag === 'pre' || tag === 'hr' || tag === 'script' || tag === 'style' || tag === 'svg' || tag === 'button') continue;
        var cls = String(el.className || '');
        if (cls.indexOf('code-copy') >= 0 || cls.indexOf('toc') >= 0) continue;
        var txt = visibleText(el, lg);
        if (!txt) continue;
        var chunks = splitText(txt, MAX_CHUNK);
        for (var k = 0; k < chunks.length; k++) list.push({ el: el, text: chunks[k] });
      }
    }
    return list;
  }

  /* ======================================================================
     9.4 播放控制
     ====================================================================== */
  var segs = [];
  var segIndex = -1;
  var playing = false;
  var paused = false;
  var utter = null;
  var curEl = null;
  var tick = null;
  var segStart = 0;

  function markCurrent(el) {
    if (curEl && curEl !== el) curEl.classList.remove('tts-current');
    curEl = el;
    if (el) {
      el.classList.add('tts-current');
      scrollIntoView(el);
    }
  }
  function clearMark() {
    if (curEl) curEl.classList.remove('tts-current');
    curEl = null;
  }
  function scrollIntoView(el) {
    var r = el.getBoundingClientRect();
    var vh = window.innerHeight || 800;
    if (r.top >= vh * 0.12 && r.bottom <= vh * 0.92) return;   // 已在视野内，不打扰阅读
    var top = (window.pageYOffset || document.documentElement.scrollTop || 0) + r.top - vh * 0.32;
    try {
      window.scrollTo({ top: Math.max(0, top), behavior: reducedMotion() ? 'auto' : 'smooth' });
    } catch (e) {
      window.scrollTo(0, Math.max(0, top));
    }
  }

  function speakAt(i) {
    if (!ttsSupported) return;
    if (i < 0 || i >= segs.length) { finish(); return; }
    segIndex = i;
    var seg = segs[i];
    markCurrent(seg.el);
    refresh();
    var u;
    try {
      u = new window.SpeechSynthesisUtterance(seg.text);
    } catch (e) { fail(); return; }
    u.rate = rate;
    u.pitch = 1;
    u.lang = lang() === 'en' ? 'en-US' : 'zh-CN';
    var v = pickVoice();
    if (v) u.voice = v;
    utter = u;
    segStart = Date.now();
    u.onend = function () { if (utter !== u) return; next(); };
    u.onerror = function (e) {
      if (utter !== u) return;
      var code = e && e.error ? e.error : '';
      if (code === 'interrupted' || code === 'canceled') return;   // 主动 cancel 不算错误
      fail();
    };
    try { synth.speak(u); } catch (e) { fail(); }
  }

  function next() {
    if (!playing) return;
    speakAt(segIndex + 1);
  }

  function finish() {
    playing = false;
    paused = false;
    stopTick();
    clearMark();
    refresh();
  }

  function fail() {
    playing = false;
    paused = false;
    stopTick();
    clearMark();
    if (synth) { try { synth.cancel(); } catch (e) {} }
    utter = null;
    segIndex = -1;
    elState.textContent = msg('error');
    refresh(true);
  }

  function play() {
    if (!ttsSupported) return;
    if (!segs.length) segs = buildSegments();
    if (!segs.length) { elState.textContent = msg('empty'); refresh(true); return; }
    if (playing && paused) {
      paused = false;
      try { synth.resume(); } catch (e) {}
      startTick();
      refresh();
      return;
    }
    if (playing) return;
    playing = true;
    paused = false;
    speakAt(segIndex >= 0 && segIndex < segs.length ? segIndex : 0);
    startTick();
    refresh();
  }

  function pause() {
    if (!playing || paused) return;
    try { synth.pause(); } catch (e) {}
    paused = true;
    refresh();
  }

  function stop(reset) {
    if (synth) { try { synth.cancel(); } catch (e) {} }
    utter = null;
    playing = false;
    paused = false;
    stopTick();
    clearMark();
    if (reset !== false) segIndex = -1;
    refresh(true);
  }

  /* Chrome 已知问题：超过约 15 秒会静默暂停 —— 每 10 秒心跳一次，
     若 paused 则 resume；若既不 speaking 也不 pending 且已超过 12 秒，视为静默中断并推进下一段。 */
  function startTick() {
    stopTick();
    tick = setInterval(function () {
      if (!playing || paused || !synth) return;
      if (synth.paused) {
        try { synth.resume(); } catch (e) {}
        return;
      }
      if (!synth.speaking && !synth.pending && (Date.now() - segStart) > 12000) next();
    }, 10000);
  }
  function stopTick() {
    if (tick) { clearInterval(tick); tick = null; }
  }

  function refresh(keepState) {
    var total = segs.length;
    var n = segIndex >= 0 ? segIndex + 1 : 0;
    if (total) {
      elCount.textContent = lang() === 'en'
        ? 'Segment ' + n + ' / ' + total
        : '第 ' + n + ' / ' + total + ' 段';
    } else elCount.textContent = '';
    elBar.style.width = total ? Math.min(100, Math.max(0, (segIndex + 1) / total * 100)) + '%' : '0%';
    if (!keepState) {
      elState.textContent = paused ? msg('paused') : (playing ? msg('playing') : (segIndex >= 0 ? msg('done') : msg('ready')));
    }
    elPlay.disabled = !ttsSupported;
    elPause.disabled = !playing || paused;
    elStop.disabled = !playing;
  }

  /* ---------- 面板按钮 ---------- */
  elPlay.addEventListener('click', play);
  elPause.addEventListener('click', pause);
  elStop.addEventListener('click', function () { stop(true); });
  panel.querySelector('.tts-close').addEventListener('click', function () { closePanel(); });

  function openPanel() {
    panel.classList.add('open');
    loadVoices();
    refresh();
    syncListenBtn();
  }
  function closePanel() {
    panel.classList.remove('open');
    stop(true);          // 关闭面板必须彻底停止朗读，不允许后台继续念
    syncListenBtn();
  }
  function togglePanel() {
    if (panel.classList.contains('open')) closePanel();
    else openPanel();
  }
  /* 工具栏「朗读」按钮与面板开合状态保持同步 */
  function syncListenBtn() {
    if (!toolButtons || !toolButtons.listen) return;
    if (panel.classList.contains('open')) toolButtons.listen.classList.add('is-active');
    else toolButtons.listen.classList.remove('is-active');
  }

  /* ======================================================================
     9.5 右侧浮动工具栏
     ====================================================================== */
  var TOOLS = [
    { key: 'listen', icon: '🔊', zh: '朗读', en: 'Listen' },
    { key: 'copy',   icon: '🔗', zh: '复制链接', en: 'Copy link' },
    { key: 'quote',  icon: '❝', zh: '引用', en: 'Quote' },
    { key: 'random', icon: '🎲', zh: '随机一篇', en: 'Random' },
    { key: 'toc',    icon: '📑', zh: '目录', en: 'Contents' },
    { key: 'top',    icon: '↑', zh: '回到顶部', en: 'Top' }
  ];

  var rail = document.createElement('div');
  rail.className = 'art-tool';
  rail.setAttribute('role', 'toolbar');
  rail.setAttribute('aria-label', '文章工具 / Article tools');

  var toolButtons = {};
  TOOLS.forEach(function (t) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'art-tool-btn';
    b.setAttribute('data-tool', t.key);
    b.setAttribute('title', t.zh + ' / ' + t.en);
    b.setAttribute('aria-label', t.zh + ' / ' + t.en);
    b.innerHTML =
      '<span class="art-tool-ico" aria-hidden="true">' + t.icon + '</span>' +
      '<span class="art-tool-tip"><span class="zh-only">' + t.zh + '</span><span class="en-only">' + t.en + '</span></span>';
    rail.appendChild(b);
    toolButtons[t.key] = b;
    b.addEventListener('click', function () { onTool(t.key, b); });
  });
  document.body.appendChild(rail);

  /* 移动端折叠按钮 */
  var fab = document.createElement('button');
  fab.type = 'button';
  fab.className = 'art-tool-fab';
  fab.setAttribute('title', '工具 / Tools');
  fab.setAttribute('aria-label', '工具 / Tools');
  fab.setAttribute('aria-expanded', 'false');
  fab.innerHTML =
    '<span class="art-tool-ico" aria-hidden="true">⚙</span>' +
    '<span class="art-tool-tip"><span class="zh-only">工具</span><span class="en-only">Tools</span></span>';
  document.body.appendChild(fab);
  fab.addEventListener('click', function () {
    var open = rail.classList.toggle('open');
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  function flash(btn, glyph, cls) {
    var ico = btn.querySelector('.art-tool-ico');
    if (!ico) return;
    var old = ico.textContent;
    ico.textContent = glyph;
    btn.classList.add(cls);
    setTimeout(function () {
      ico.textContent = old;
      btn.classList.remove(cls);
    }, 1600);
  }

  function quoteText() {
    var title = self ? (lang() === 'en' ? self.en : self.zh) : (document.title || '');
    var name = self ? self.file : (location.pathname.split('/').pop() || '');
    return '> ' + title + ' —— 木尘 · AI 编程实践者\n> https://muchengit.github.io/blog/' + name;
  }

  function onTool(key, btn) {
    if (key === 'listen') { togglePanel(); syncListenBtn(); return; }
    if (key === 'copy') {
      copyText(location.href, function () { flash(btn, '✓', 'is-ok'); }, function () { flash(btn, '✕', 'is-ok'); });
      return;
    }
    if (key === 'quote') {
      copyText(quoteText(), function () { flash(btn, '✓', 'is-ok'); }, function () { flash(btn, '✕', 'is-ok'); });
      return;
    }
    if (key === 'random') {
      var pool = [];
      for (var i = 0; i < ARTICLES.length; i++) {
        if (String(ARTICLES[i].file).toLowerCase() !== here) pool.push(ARTICLES[i]);
      }
      if (!pool.length) return;
      location.href = pool[Math.floor(Math.random() * pool.length)].file;
      return;
    }
    if (key === 'toc') {
      var toc = document.querySelector('.toc');
      if (!toc) return;
      try {
        toc.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
      } catch (e) { toc.scrollIntoView(true); }
      return;
    }
    if (key === 'top') {
      var toTop = document.querySelector('.to-top');
      if (toTop) toTop.click();          // 复用页面已有的回到顶部按钮
    }
  }

  /* ---------- 初始状态 ---------- */
  if (!ttsSupported) {
    toolButtons.listen.disabled = true;
    toolButtons.listen.setAttribute('title', '当前浏览器不支持朗读 / This browser does not support speech');
    toolButtons.listen.setAttribute('aria-label', '当前浏览器不支持朗读 / This browser does not support speech');
    elPlay.disabled = true;
  }
  if (!document.querySelector('.toc')) {
    toolButtons.toc.disabled = true;
    toolButtons.toc.setAttribute('title', '本页没有目录 / No table of contents');
    toolButtons.toc.setAttribute('aria-label', '本页没有目录 / No table of contents');
  }
  var others = 0;
  for (var k = 0; k < ARTICLES.length; k++) if (String(ARTICLES[k].file).toLowerCase() !== here) others++;
  if (!others) {
    toolButtons.random.disabled = true;
    toolButtons.random.setAttribute('title', '没有其他文章 / No other article');
    toolButtons.random.setAttribute('aria-label', '没有其他文章 / No other article');
  }

  /* ---------- 语言切换：停止当前朗读并重建语音列表 ---------- */
  if (window.MutationObserver) {
    var langObserver = new MutationObserver(function () {
      if (playing || paused) {
        stop(true);
        elState.textContent = msg('again');
      }
      segs = [];          // 语言变了，正文分段必须按新语言重建
      segIndex = -1;
      fillVoices();
      refresh(true);
    });
    langObserver.observe(document.body, { attributes: true, attributeFilter: ['data-lang'] });
  }

  /* ---------- 离开页面时确保不再朗读 ---------- */
  window.addEventListener('pagehide', function () { stop(true); });

  refresh();
})();
