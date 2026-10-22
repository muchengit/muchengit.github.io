/**
 * Service Worker — 木尘 · AI 编程实践者 (https://muchengit.github.io/)
 *
 * 用途：
 *   1. install 阶段预缓存站点核心壳（首页 / 文章归档 / 分类 / 标签 / 实验室 / 图标 / RSS），
 *      让站点可被安装到桌面或手机主屏，并在离线时仍可阅读。
 *   2. fetch 阶段按资源类型分流：
 *      - 导航请求（mode === 'navigate'）：network-first，网络失败回退缓存的首页，
 *        再回退到 /offline.html（该文件若不存在则静默回退到首页）。
 *      - 静态资源（js/css/png/jpg/svg/ico/woff 等）：stale-while-revalidate，
 *        先给缓存再后台刷新。
 *      - 其余请求：直接走网络，不做缓存。
 *
 * 更新方式：
 *   修改任何被缓存的内容后，把下面的 CACHE 版本号改成新的日期版本（如 'muchengit-v1-20261023'），
 *   浏览器会在下次访问时重新预缓存，并由 activate 阶段自动清理旧版本缓存。
 *   若希望立即接管，可让页面向 Service Worker 发送 { type: 'SKIP_WAITING' } 消息。
 *
 * 纯 Worker 实现，不依赖 DOM，也不使用任何外部脚本。
 */

const CACHE = 'muchengit-v3-20261022';

const HOME_URL = '/';
const OFFLINE_URL = '/offline.html';

/** 预缓存的核心壳。逐个添加：其中任一 URL 不存在都不会导致整个安装失败。 */
const PRECACHE_URLS = [
  HOME_URL,
  '/blog/',
  '/blog/categories.html',
  '/blog/tags.html',
  '/blog/popular.html',
  '/lab.html',
  '/favicon.svg',
  '/assets/icon-192.png',
  '/assets/theme.css',
  '/assets/theme.js',
  '/feed.xml',
  OFFLINE_URL,
];

/** 可走 stale-while-revalidate 的静态资源扩展名。 */
const STATIC_RE = /\.(?:js|mjs|css|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|eot)$/i;

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      await Promise.allSettled(
        PRECACHE_URLS.map(async (url) => {
          try {
            // cache:'reload' 绕过 HTTP 缓存，保证拿到最新版本
            const response = await fetch(new Request(url, { cache: 'reload', credentials: 'same-origin' }));
            // 只缓存同源的成功响应；404 / opaque 响应原样跳过
            if (response && response.ok && response.type === 'basic') {
              await cache.put(url, response.clone());
            }
          } catch (err) {
            // 单个资源失败（例如 /offline.html 尚未创建）时忽略，不影响整体安装
          }
        })
      );
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', (event) => {
  const request = event.request;

  // 只处理 GET
  if (request.method !== 'GET') return;

  let url;
  try {
    url = new URL(request.url);
  } catch (err) {
    return;
  }

  // 只处理同源请求
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(handleNavigate(event, request));
    return;
  }

  if (STATIC_RE.test(url.pathname)) {
    event.respondWith(handleStatic(event, request));
    return;
  }

  // 其余请求（表单、接口等）直接走网络，不拦截
});

/**
 * 导航请求：network-first。
 * 网络失败时依次回退：缓存的首页 -> 缓存的 /offline.html -> 首页（静默回退）。
 */
async function handleNavigate(event, request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok && response.type === 'basic') {
      cache.put(request, response.clone()).catch(() => {});
    }
    return response;
  } catch (err) {
    const cachedHome = await cache.match(HOME_URL);
    if (cachedHome) return cachedHome;

    const cachedOffline = await cache.match(OFFLINE_URL);
    if (cachedOffline) return cachedOffline;

    // /offline.html 未缓存时静默回退到首页
    const fallbackHome = await cache.match(HOME_URL);
    if (fallbackHome) return fallbackHome;

    return new Response(
      '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">' +
        '<meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<title>离线 · 木尘</title></head><body style="background:#0A0E1A;color:#E6EDF3;' +
        'font-family:system-ui,-apple-system,sans-serif;padding:2rem">' +
        '<h1>当前处于离线状态</h1><p>该页面尚未缓存，联网后再试。</p></body></html>',
      { status: 503, statusText: 'Service Unavailable', headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}

/**
 * 静态资源：stale-while-revalidate —— 先返回缓存，后台静默更新缓存。
 */
async function handleStatic(event, request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);

  const network = fetch(request)
    .then((response) => {
      // 仅缓存成功且非 opaque 的响应，其余原样返回
      if (response && response.ok && response.type === 'basic') {
        cache.put(request, response.clone()).catch(() => {});
      }
      return response;
    })
    .catch(() => null);

  if (cached) {
    event.waitUntil(network.then(() => undefined));
    return cached;
  }

  const response = await network;
  if (response) return response;

  return new Response('', { status: 504, statusText: 'Gateway Timeout' });
}
