/* ==========================================================================
   theme.js — 皮肤系统（主题色板 + 皮肤选择器）
   注入方式：所有页面在 </body> 前引入 <script src=".../assets/theme.js"></script>

   - 皮肤写在 <html data-skin="..."> 上，浅色系额外带 data-tone="light"
   - 选择持久化在 localStorage['site-skin']，值为 'auto' 或具体皮肤 id
   - 'auto' 跟随系统 prefers-color-scheme（暗 → 深空，亮 → 纸白）
   - 支持 ?skin=twilight 临时预览（不写入 localStorage）
   - 注意：本文件不要注册 #langBtn 的 click 事件（各页内联脚本已注册过）
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'site-skin';

  /* ---------------- 皮肤表 ---------------- */
  var SKINS = [
    { id: 'midnight', zh: '深空', en: 'Midnight', tone: 'dark',
      sw: { bg: '#0A0E1A', bg2: '#0F1524', glow: 'rgba(0,229,255,.45)', accent: '#00E5FF', accent2: '#A855F7' },
      bar: '#0A0E1A' },
    { id: 'twilight', zh: '暮紫', en: 'Twilight', tone: 'dark',
      sw: { bg: '#120A1E', bg2: '#1B1030', glow: 'rgba(192,132,252,.45)', accent: '#C084FC', accent2: '#F472B6' },
      bar: '#120A1E' },
    { id: 'forest', zh: '墨绿', en: 'Forest', tone: 'dark',
      sw: { bg: '#06120E', bg2: '#0C2019', glow: 'rgba(52,211,153,.45)', accent: '#34D399', accent2: '#2DD4BF' },
      bar: '#06120E' },
    { id: 'sunset', zh: '暖阳', en: 'Sunset', tone: 'dark',
      sw: { bg: '#150C0A', bg2: '#241410', glow: 'rgba(253,186,116,.45)', accent: '#FDBA74', accent2: '#F472B6' },
      bar: '#150C0A' },
    { id: 'paper', zh: '纸白', en: 'Paper', tone: 'light',
      sw: { bg: '#F3F6FC', bg2: '#FFFFFF', glow: 'rgba(11,127,168,.30)', accent: '#0B7FA8', accent2: '#7C3AED' },
      bar: '#F3F6FC' },
    { id: 'dawn', zh: '晨曦', en: 'Dawn', tone: 'light',
      sw: { bg: '#FBF6EF', bg2: '#FFFFFF', glow: 'rgba(251,191,36,.40)', accent: '#B45309', accent2: '#9333EA' },
      bar: '#FBF6EF' }
  ];
  var BY_ID = {};
  SKINS.forEach(function (s) { BY_ID[s.id] = s; });

  var root = document.documentElement;
  var mql = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;

  /* ---------------- 存储 ---------------- */
  function read() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function save(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* ignore */ }
  }

  /* ---------------- 应用 ---------------- */
  function resolve(id) {
    if (id === 'auto') return (mql && mql.matches) ? 'paper' : 'midnight';
    return BY_ID[id] ? id : 'midnight';
  }

  function apply(id, animate) {
    var real = resolve(id);
    var skin = BY_ID[real];
    root.setAttribute('data-skin', real);
    root.setAttribute('data-tone', skin.tone);
    if (animate) {
      root.classList.add('theme-anim');
      window.setTimeout(function () { root.classList.remove('theme-anim'); }, 340);
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', skin.bar);
    var btn = document.getElementById('skinBtn');
    if (btn) btn.setAttribute('aria-label', skinLabel(real));
    var cur = document.getElementById('skinCurrent');
    if (cur) {
      cur.textContent = skin.zh;
      var curEn = cur.parentNode.querySelector('.skin-name-en');
      if (curEn) curEn.textContent = skin.en;
    }    markActive(real);
  }

  function skinLabel(real) {
    var s = BY_ID[real];
    return '皮肤 / Skin — ' + s.zh + ' ' + s.en;
  }

  /* ---------------- 选择器 UI ---------------- */
  var panel = null, btn = null, saved = read();

  function build() {
    btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'skinBtn';
    btn.className = 'skin-btn';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', '皮肤 / Skin');
    btn.title = '皮肤 / Skin';
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" width="17" height="17">' +
      '<path d="M12 21a9 9 0 1 1 9-9c0 1.7-1.3 3-3 3h-1.5a2 2 0 0 0-1.4 3.4c.3.3.4.7.4 1.1 0 .8-.7 1.5-1.5 1.5H12Z"/>' +
      '<circle cx="7.5" cy="12.5" r="1.1"/><circle cx="9.8" cy="8.2" r="1.1"/><circle cx="14.5" cy="7.8" r="1.1"/>' +
      '</svg>';

    panel = document.createElement('div');
    panel.className = 'skin-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', '选择皮肤 / Choose a skin');
    panel.innerHTML =
      '<h3><span><span class="zh-only">皮肤</span><span class="en-only">Skin</span></span>' +
      '<span class="skin-current"><span class="skin-name-zh" id="skinCurrent">深空</span>' +
      '<span class="skin-name-en"></span></span></h3>' +
      '<p class="sp-sub"><span class="zh-only">换个底色与强调色，页面配色立刻换一套。</span>' +
      '<span class="en-only">Swap the background and accent — the whole page follows.</span></p>' +
      '<div class="skin-grid" role="listbox"></div>' +
      '<div class="skin-auto">' +
      '  <span class="sa-t"><b><span class="zh-only">跟随系统</span><span class="en-only">Follow system</span></b>' +
      '<span class="zh-only">暗色自动用深空，亮色自动用纸白</span>' +
      '<span class="en-only">Dark → Midnight, light → Paper</span></span>' +
      '  <button type="button" class="skin-switch" id="skinAuto" role="switch" aria-checked="false" ' +
      'aria-label="跟随系统 / Follow system"></button>' +
      '</div>';

    var grid = panel.querySelector('.skin-grid');
    SKINS.forEach(function (s) {
      var card = document.createElement('button');
      card.type = 'button';
      card.className = 'skin-card';
      card.setAttribute('role', 'option');
      card.setAttribute('data-skin-id', s.id);
      card.setAttribute('aria-selected', 'false');
      card.style.setProperty('--s-bg', s.sw.bg);
      card.style.setProperty('--s-bg2', s.sw.bg2);
      card.style.setProperty('--s-glow', s.sw.glow);
      card.style.setProperty('--s-accent', s.sw.accent);
      card.style.setProperty('--s-accent2', s.sw.accent2);
      card.innerHTML =
        '<span class="skin-check" aria-hidden="true">✓</span>' +
        '<span class="skin-sw" aria-hidden="true"></span>' +
        '<span class="skin-name"><span class="zh-only">' + s.zh + '</span>' +
        '<span class="en-only">' + s.en + '</span></span>';

      card.addEventListener('click', function () {
        saved = s.id;
        save(s.id);
        apply(s.id, true);
        syncAuto();
        close();
      });
      /* 悬停实时预览，移开恢复 */
      card.addEventListener('mouseenter', function () { apply(s.id, false); });
      card.addEventListener('focus', function () { apply(s.id, false); });
      card.addEventListener('mouseleave', function () { apply(saved === 'auto' ? 'auto' : saved, false); });
      card.addEventListener('blur', function () { apply(saved === 'auto' ? 'auto' : saved, false); });
      grid.appendChild(card);
    });

    var autoBtn = panel.querySelector('#skinAuto');
    autoBtn.addEventListener('click', function () {
      saved = 'auto';
      save('auto');
      apply('auto', true);
      syncAuto();
    });

    document.body.appendChild(panel);

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      panel.classList.contains('open') ? close() : open();
    });
    document.addEventListener('click', function (e) {
      if (!panel.classList.contains('open')) return;
      if (panel.contains(e.target) || btn.contains(e.target)) return;
      close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && panel.classList.contains('open')) { close(); btn.focus(); }
    });

    if (mql && mql.addEventListener) {
      mql.addEventListener('change', function () { if (saved === 'auto') apply('auto', false); });
    }
  }

  function open() {
    panel.classList.add('open');
    btn.setAttribute('aria-expanded', 'true');
    /* 打开时把鼠标预览恢复成当前选择 */
    apply(saved === 'auto' ? 'auto' : saved, false);
  }
  function close() {
    panel.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  }

  function markActive(real) {
    if (!panel) return;
    var cards = panel.querySelectorAll('.skin-card');
    Array.prototype.forEach.call(cards, function (c) {
      var on = c.getAttribute('data-skin-id') === real;
      c.classList.toggle('active', on);
      c.setAttribute('aria-selected', on ? 'true' : 'false');
    });
  }

  function syncAuto() {
    if (!panel) return;
    var sw = panel.querySelector('#skinAuto');
    if (sw) sw.setAttribute('aria-checked', saved === 'auto' ? 'true' : 'false');
  }

  function mount() {
    if (document.getElementById('skinBtn')) return;
    var host = document.querySelector('.nav-right');
    if (!host) return;
    build();
    host.insertBefore(btn, host.firstChild);
    var langBtn = document.getElementById('langBtn');
    if (langBtn && langBtn.parentNode === host) host.insertBefore(btn, langBtn);
    syncAuto();
    /* 面板建好后再跑一次 apply，把当前皮肤的中英文名填进面板标题 */
    apply(saved === 'auto' ? 'auto' : saved, false);
    markActive(resolve(saved));
    /* 预览用：?picker=1 直接展开选择面板 */
    try {
      if (/[?&]picker=1/.test(location.search)) setTimeout(open, 120);
    } catch (e) { /* ignore */ }
  }

  /* ---------------- 初始化 ---------------- */
  var preview = '';
  try {
    preview = (location.search.match(/[?&]skin=([a-z]+)/) || [])[1] || '';
    if (!preview) {
      var t = (location.search.match(/[?&]theme=(light|dark)/) || [])[1] || '';
      preview = t === 'light' ? 'paper' : (t === 'dark' ? 'midnight' : '');
    }
  } catch (e) { preview = ''; }

  if (preview && (BY_ID[preview] || preview === 'auto')) {
    saved = preview;                       /* 预览模式：不写入 localStorage */
    apply(preview, false);
  } else {
    if (!saved || (saved !== 'auto' && !BY_ID[saved])) saved = 'midnight';
    apply(saved, false);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
