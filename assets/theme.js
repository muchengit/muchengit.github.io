/* ==========================================================================
   theme.js — 浅色 / 深色主题切换
   注入方式：所有页面在 </body> 前引入 <script src=".../assets/theme.js"></script>
   - 读取 localStorage['site-theme']（'light' / 'dark'），默认深色（品牌基色）
   - 在 <html> 上设置 data-theme="light"
   - 把切换按钮注入 .nav-right（语言按钮左侧）
   注意：本文件不要注册 #langBtn 的 click 事件（各页内联脚本已注册过）。
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'site-theme';
  var root = document.documentElement;

  function read() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function save(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* ignore */ }
  }

  function apply(theme, animate) {
    if (theme === 'light') root.setAttribute('data-theme', 'light');
    else root.removeAttribute('data-theme');
    if (animate) {
      root.classList.add('theme-anim');
      window.setTimeout(function () { root.classList.remove('theme-anim'); }, 320);
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'light' ? '#F3F6FC' : '#0A0E1A');
    var btn = document.getElementById('themeBtn');
    if (btn) btn.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');
  }

  var saved = read();
  /* 支持 ?theme=light / ?theme=dark 临时预览（不写入 localStorage） */
  var preview = '';
  try {
    preview = (location.search.match(/[?&]theme=(light|dark)/) || [])[1] || '';
  } catch (e) { preview = ''; }
  apply(preview === 'light' ? 'light' : (preview === 'dark' ? 'dark' : (saved === 'light' ? 'light' : 'dark')), false);

  function mount() {
    if (document.getElementById('themeBtn')) return;
    var host = document.querySelector('.nav-right');
    if (!host) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'themeBtn';
    btn.className = 'theme-btn';
    btn.setAttribute('aria-label', '切换深色 / 浅色主题');
    btn.setAttribute('title', '切换深色 / 浅色主题');
    btn.innerHTML =
      '<span class="ic ic-dark" aria-hidden="true">&#9789;</span>' +
      '<span class="ic ic-light" aria-hidden="true">&#9788;</span>';

    var langBtn = document.getElementById('langBtn');
    if (langBtn && langBtn.parentNode === host) host.insertBefore(btn, langBtn);
    else host.insertBefore(btn, host.firstChild);

    btn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      save(next);
      apply(next, true);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
