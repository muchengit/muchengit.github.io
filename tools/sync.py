#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.py — 站点内容同步器（唯一内容真源）
扫描 blog/ 下的文章文件，自动重建：
  1. blog/articles.js        文章清单（日期倒序，含字数与标签）
  2. index.html             首页「文章」板块 + 内容索引条
  3. blog/index.html        文章归档页（按年份分组的静态列表）
  4. blog/categories.html   分类总览页
  5. blog/tags.html         标签页
  6. blog/popular.html      精选 / 阅读路线页
  7. feed.xml               RSS 订阅源
  8. sitemap.xml            站点地图
另外统一维护：站点导航、博客页脚、主题资源引用、PWA 注册。

数据来源：
  tools/tagmap.json   文章 → 标签映射（人工维护）
  tools/curated.json  分类描述 / 精选名单 / 阅读路线（人工维护）

用法：  python3 tools/sync.py
"""
import re, os, glob, json, datetime, html, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG = os.path.join(ROOT, "blog")
BASE = "https://muchengit.github.io"
CJK = re.compile(r'[\u4e00-\u9fa5\u3040-\u30ff]')

# 首页「文章」板块展示每年最多多少篇
HOME_PER_YEAR = {"2026": 12, "2025": 3, "2024": 3}

# 分类中文 → 英文（与站点分类体系保持一致）
CAT_EN = {
    "入门": "Getting Started", "产品": "Product", "实战": "Case Study",
    "AI 编程": "AI Coding", "工具评测": "Tools", "AI 技巧": "Tips",
    "Agent": "Agent", "独立开发": "Indie Dev", "出海": "Global",
    "副业": "Side Hustle", "趋势": "Trends", "深度解析": "Deep Dive",
    "年度总结": "Year in Review", "视频生成": "Video AI", "AI 绘画": "AI Art",
    "工具栈": "Toolkit",
}

# 分类的展示顺序（数量相同时按此顺序排）
CAT_ORDER = list(CAT_EN.keys())

# 博客页统一导航
BLOG_NAV = [
    ("archive", "index.html", "归档", "Archive"),
    ("categories", "categories.html", "分类", "Categories"),
    ("tags", "tags.html", "标签", "Tags"),
    ("popular", "popular.html", "精选", "Featured"),
    ("lab", "../lab.html", "实验室", "Lab"),
    ("about", "../#about", "关于", "About"),
]


# ==========================================================================
# 工具函数
# ==========================================================================
def strip_tags(s):
    s = re.sub(r'<span class="en-only">.*?</span>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def js_str(s):
    """安全地把字符串写进 JS 字面量"""
    return json.dumps(str(s), ensure_ascii=False)


def esc_html(s):
    return html.escape(str(s), quote=True)


def load_json(path, default):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"   ⚠️  {path} 解析失败：{e}")
        return default


# ==========================================================================
# 文章解析
# ==========================================================================
def parse_article(path, tagmap):
    src = open(path, encoding="utf-8").read()
    name = os.path.basename(path)

    h1 = re.search(r'<h1 class="reveal">(.*?)</h1>', src, re.S)
    if not h1:
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', src, re.S)
    zh = en = ""
    if h1:
        m = re.search(r'<span class="zh-only">(.*?)</span>', h1.group(1), re.S)
        zh = strip_tags(m.group(1)) if m else ""
        m = re.search(r'<span class="en-only">(.*?)</span>', h1.group(1), re.S)
        en = strip_tags(m.group(1)) if m else ""

    dm = re.search(r'(20\d\d\.\d\d\.\d\d)', src)
    date = dm.group(1) if dm else "1970.01.01"

    cat = ""
    tm = re.search(r'<div class="tag">(.*?)</div>', src, re.S)
    if tm:
        m = re.search(r'<span class="zh-only">(.*?)</span>', tm.group(1), re.S)
        if m:
            cat = strip_tags(m.group(1))
        else:
            cat = re.sub(r'<[^>]+>', '', tm.group(1)).split("|")[0].strip()
    cat_en = CAT_EN.get(cat, cat)

    # 中文字数（只算正文，不含导航 / 页脚 / 脚本）
    am = re.search(r'<article[^>]*>(.*?)</article>', src, re.S)
    body = am.group(1) if am else src
    z = re.sub(r'<span class="en-only">.*?</span>', '', body, flags=re.S)
    z = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', z, flags=re.S)
    z = re.sub(r'<[^>]+>', ' ', z)
    words = len(CJK.findall(z))

    # 简介：正文第一段
    desc_zh = desc_en = ""
    secs = re.findall(r'<section class="prose[^"]*">(.*?)</section>', src, re.S)
    for sec in secs:
        ps = re.findall(r'<p>(.*?)</p>', sec, re.S)
        if not ps:
            continue
        p = ps[0]
        m = re.search(r'<span class="zh-only">(.*?)</span>', p, re.S)
        if m and len(strip_tags(m.group(1))) > 20:
            desc_zh = strip_tags(m.group(1))
        m = re.search(r'<span class="en-only">(.*?)</span>', p, re.S)
        if m and len(strip_tags(m.group(1))) > 20:
            desc_en = strip_tags(m.group(1))
        if desc_zh and desc_en:
            break
    if not desc_en:
        desc_en = en
    if not desc_zh:
        desc_zh = zh
    if len(desc_zh) > 72:
        desc_zh = desc_zh[:72].rstrip("，,、 ") + "…"
    if len(desc_en) > 110:
        desc_en = desc_en[:110].rstrip("，, ") + "…"

    tags = list(tagmap.get(name, []))

    return dict(file=name, date=date, cat=cat, catEn=cat_en, zh=zh, en=en,
                words=words, descZh=desc_zh, descEn=desc_en, tags=tags)


def collect(tagmap):
    arts = []
    for p in sorted(glob.glob(os.path.join(BLOG, "*.html"))):
        base = os.path.basename(p)
        if base in ("index.html", "categories.html", "tags.html", "popular.html"):
            continue
        arts.append(parse_article(p, tagmap))
    arts.sort(key=lambda a: (a["date"], a["file"]), reverse=True)
    return arts


# ==========================================================================
# 数据分组
# ==========================================================================
def group_by_cat(arts):
    """分类 → 文章列表（按文章数倒序，篇数相同时按 CAT_ORDER）"""
    buckets = {}
    for a in arts:
        if not a["cat"]:
            continue
        buckets.setdefault(a["cat"], []).append(a)
    order = {c: i for i, c in enumerate(CAT_ORDER)}
    return sorted(buckets.items(),
                  key=lambda kv: (-len(kv[1]), order.get(kv[0], 999), kv[0]))


def group_by_tag(arts):
    """标签 → 文章列表（按文章数倒序，标签字典序）"""
    buckets = {}
    for a in arts:
        for t in a["tags"]:
            buckets.setdefault(t, []).append(a)
    return sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0]))


# ==========================================================================
# 文章清单 JS
# ==========================================================================
def write_articles_js(arts):
    lines = ["/* 文章清单 — 供 blog.js / archive.js 与 tools/sync.py 使用",
             "   字段：file 文件名, date 发布日期, cat 分类, catEn 分类英文, words 正文字数,",
             "         zh 中文标题, en 英文标题, tags 标签数组",
             "   本文件由 tools/sync.py 自动生成，请勿手工编辑 */",
             "window.SITE_ARTICLES = ["]
    for a in arts:
        lines.append(
            '  {file:%s, date:%s, cat:%s, catEn:%s, words:%d, zh:%s, en:%s, tags:[%s]},'
            % (js_str(a["file"]), js_str(a["date"]), js_str(a["cat"]), js_str(a["catEn"]),
               a["words"], js_str(a["zh"]), js_str(a["en"]),
               ",".join(js_str(t) for t in a["tags"])))
    lines.append("];")
    open(os.path.join(BLOG, "articles.js"), "w", encoding="utf-8").write("\n".join(lines))


# ==========================================================================
# 首页 / 归档页
# ==========================================================================
def build_home_groups(arts):
    groups = []
    for year in sorted({a["date"][:4] for a in arts}, reverse=True):
        limit = HOME_PER_YEAR.get(year, 5)
        items = [a for a in arts if a["date"][:4] == year][:limit]
        if not items:
            continue
        rows = []
        for a in items:
            rows.append(
                '        <a href="blog/%s" class="post reveal"><span class="date">%s</span>'
                '<div class="info"><h3><span class="zh-only">%s</span><span class="en-only">%s</span></h3>'
                '<p><span class="zh-only">%s</span><span class="en-only">%s</span></p></div>'
                '<span class="cat"><span class="zh-only">%s</span><span class="en-only">%s</span></span></a>'
                % (a["file"], a["date"], esc_html(a["zh"]), esc_html(a["en"]),
                   esc_html(a["descZh"]), esc_html(a["descEn"]),
                   esc_html(a["cat"]), esc_html(a["catEn"])))
        groups.append(
            '    <div class="post-group reveal">\n'
            '      <div class="post-year">%s</div>\n'
            '      <div class="posts">\n\n%s\n\n      </div>\n    </div>'
            % (year, "\n\n".join(rows)))
    return "\n\n".join(groups)


def build_archive_groups(arts):
    groups = []
    for year in sorted({a["date"][:4] for a in arts}, reverse=True):
        items = [a for a in arts if a["date"][:4] == year]
        rows = []
        for a in items:
            rows.append(
                '        <a class="post" href="%s" data-year="%s" data-cat="%s" data-cat-en="%s" data-tags="%s">\n'
                '          <span class="post-date">%s</span>\n'
                '          <h3 class="post-title"><span class="zh-only">%s</span><span class="en-only">%s</span></h3>\n'
                '          <span class="post-cat"><span class="zh-only">%s</span><span class="en-only">%s</span></span>\n'
                '          <p class="post-desc"><span class="zh-only">%s</span><span class="en-only">%s</span></p>\n'
                '          <span class="post-arrow" aria-hidden="true">&rarr;</span>\n'
                '        </a>'
                % (a["file"], year, esc_html(a["cat"]), esc_html(a["catEn"]),
                   esc_html("|".join(a["tags"])), a["date"],
                   esc_html(a["zh"]), esc_html(a["en"]),
                   esc_html(a["cat"]), esc_html(a["catEn"]),
                   esc_html(a["descZh"]), esc_html(a["descEn"])))
        groups.append(
            '    <section class="ygroup" data-year="%s">\n'
            '      <h2 class="yhead"><span class="yyear">%s</span><span class="yn">'
            '<span class="zh-only">共 <b class="yn-count">%d</b> 篇</span>'
            '<span class="en-only"><b class="yn-count">%d</b> articles</span></span></h2>\n'
            '      <div class="posts">\n%s\n      </div>\n    </section>'
            % (year, year, len(items), len(items), "\n".join(rows)))
    return "\n".join(groups)


# ==========================================================================
# 分类总览页
# ==========================================================================
def build_categories_html(arts, curated):
    cats = curated.get("categories", {}) if isinstance(curated, dict) else {}
    groups = group_by_cat(arts)
    by_file = {a["file"]: a for a in arts}
    cards = []

    for idx, (cat, items) in enumerate(groups):
        info = cats.get(cat, {})
        desc_zh = info.get("descZh") or f"{cat}方向的文章，共 {len(items)} 篇。"
        desc_en = info.get("descEn") or info.get("en") or f"Articles in {cat}: {len(items)}."
        icon = info.get("icon") or "📄"
        words = sum(a["words"] for a in items)
        minutes = max(1, round(words / 400))

        feat = [f for f in info.get("featured", []) if f in by_file][:3]
        if not feat:
            feat = [a["file"] for a in items[:3]]
        li = []
        for f in feat:
            a = by_file[f]
            li.append(
                '          <li><a href="%s"><span class="zh-only">%s</span><span class="en-only">%s</span></a>'
                '<span class="d">%s</span></li>'
                % (a["file"], esc_html(a["zh"]), esc_html(a["en"]), a["date"]))

        cards.append(
            '    <div class="cat-card reveal" id="cat-%d">\n'
            '      <div class="cat-top">\n'
            '        <span class="cat-ic" aria-hidden="true">%s</span>\n'
            '        <h2 class="cat-name"><span class="zh-only">%s</span><span class="en-only">%s</span></h2>\n'
            '        <span class="cat-n"><b>%d</b><span class="zh-only">篇</span><span class="en-only">posts</span></span>\n'
            '      </div>\n'
            '      <p class="cat-desc"><span class="zh-only">%s</span><span class="en-only">%s</span></p>\n'
            '      <div class="cat-stats">\n'
            '        <span><span class="zh-only">%s 字</span><span class="en-only">%s words</span></span>\n'
            '        <span><span class="zh-only">约 %d 分钟</span><span class="en-only">~%d min</span></span>\n'
            '      </div>\n'
            '      <ul class="cat-list">\n%s\n      </ul>\n'
            '      <a class="cat-more" href="index.html?cat=%s">'
            '<span class="zh-only">查看该分类全部文章 →</span>'
            '<span class="en-only">See all %s articles →</span></a>\n'
            '    </div>'
            % (idx + 1, icon, esc_html(cat), esc_html(info.get("en") or CAT_EN.get(cat, cat)),
               len(items), esc_html(desc_zh), esc_html(desc_en),
               "{:,}".format(words), "{:,}".format(words), minutes, minutes,
               "\n".join(li),
               urllib_quote(cat), esc_html(info.get("en") or CAT_EN.get(cat, cat))))

    return ('  <div class="cat-grid">\n\n' + "\n\n".join(cards) + '\n\n  </div>')


def urllib_quote(s):
    from urllib.parse import quote
    return quote(str(s), safe="")


# ==========================================================================
# 标签页
# ==========================================================================
def build_tags_html(arts):
    groups = group_by_tag(arts)
    by_file = {a["file"]: a for a in arts}
    maxn = max([len(v) for _, v in groups], default=1)
    minn = min([len(v) for _, v in groups], default=1)

    cloud = []
    for idx, (tag, items) in enumerate(groups):
        ratio = 1.0 if maxn == minn else (len(items) - minn) / (maxn - minn)
        scale = 0.82 + ratio * 0.5
        cloud.append(
            '      <a class="tg reveal" href="#tag-%d" style="--tg-scale:%.2f">'
            '<span class="tg-name">%s</span><span class="tg-n">%d</span></a>'
            % (idx + 1, scale, esc_html(tag), len(items)))

    blocks = []
    for idx, (tag, items) in enumerate(groups):
        lis = []
        for a in items:
            lis.append(
                '          <li><a href="%s"><span class="zh-only">%s</span>'
                '<span class="en-only">%s</span></a>'
                '<span class="d">%s</span><span class="c">%s</span></li>'
                % (a["file"], esc_html(a["zh"]), esc_html(a["en"]), a["date"], esc_html(a["cat"])))
        blocks.append(
            '    <details class="tag-block reveal" id="tag-%d">\n'
            '      <summary><span class="tb-name">%s</span>'
            '<span class="tb-n"><span class="zh-only">%d 篇</span><span class="en-only">%d articles</span></span></summary>\n'
            '      <ul class="tb-list">\n%s\n      </ul>\n'
            '    </details>'
            % (idx + 1, esc_html(tag), len(items), len(items), "\n".join(lis)))

    return ('  <div class="tag-cloud" id="tagCloud">\n' + "\n".join(cloud) +
            '\n  </div>\n\n  <div class="tag-blocks">\n' + "\n".join(blocks) + '\n  </div>')


# ==========================================================================
# 精选页
# ==========================================================================
def build_popular_html(arts, curated):
    by_file = {a["file"]: a for a in arts}
    curated = curated if isinstance(curated, dict) else {}

    # ---- 全站精选 ----
    feat_items = []
    for i, f in enumerate(curated.get("featured", [])):
        a = by_file.get(f.get("file"))
        if not a:
            continue
        reason_zh = f.get("reasonZh") or ""
        reason_en = f.get("reasonEn") or ""
        feat_items.append(
            '      <li class="pop-item reveal">\n'
            '        <span class="pop-rank">%02d</span>\n'
            '        <div class="pop-body">\n'
            '          <h3><a href="%s"><span class="zh-only">%s</span><span class="en-only">%s</span></a></h3>\n'
            '          <p class="pop-reason"><span class="zh-only">%s</span><span class="en-only">%s</span></p>\n'
            '          <span class="pop-meta"><span class="d">%s</span><span class="c">%s</span>'
            '<span class="w"><span class="zh-only">%s 字</span><span class="en-only">%s words</span></span></span>\n'
            '        </div>\n'
            '      </li>'
            % (i + 1, a["file"], esc_html(a["zh"]), esc_html(a["en"]),
               esc_html(reason_zh), esc_html(reason_en),
               a["date"], esc_html(a["cat"]), "{:,}".format(a["words"]), "{:,}".format(a["words"])))

    feat_html = (
        '  <section class="pop-sec reveal">\n'
        '    <div class="pop-head"><span class="pop-kicker">FEATURED</span>'
        '<h2><span class="zh-only">全站精选</span><span class="en-only">Hand-picked</span></h2>'
        '<p class="pop-sub"><span class="zh-only">如果只读十篇，就读这十篇。</span>'
        '<span class="en-only">If you only read ten, read these ten.</span></p></div>\n'
        '    <ol class="pop-list">\n' + "\n".join(feat_items) + '\n    </ol>\n  </section>')

    # ---- 阅读路线 ----
    path_cards = []
    for p in curated.get("paths", []):
        steps = []
        for s in p.get("steps", []):
            a = by_file.get(s.get("file"))
            if not a:
                continue
            steps.append(
                '            <li><a href="%s"><span class="zh-only">%s</span>'
                '<span class="en-only">%s</span></a>'
                '<span class="note"><span class="zh-only">%s</span><span class="en-only">%s</span></span></li>'
                % (a["file"], esc_html(a["zh"]), esc_html(a["en"]),
                   esc_html(s.get("noteZh", "")), esc_html(s.get("noteEn", ""))))
        if not steps:
            continue
        path_cards.append(
            '      <article class="path-card reveal">\n'
            '        <span class="path-level">%s</span>\n'
            '        <h3><span class="zh-only">%s</span><span class="en-only">%s</span></h3>\n'
            '        <p class="path-desc"><span class="zh-only">%s</span><span class="en-only">%s</span></p>\n'
            '        <ol class="path-steps">\n%s\n        </ol>\n'
            '      </article>'
            % (esc_html(p.get("level", "")), esc_html(p.get("titleZh", "")), esc_html(p.get("titleEn", "")),
               esc_html(p.get("descZh", "")), esc_html(p.get("descEn", "")),
               "\n".join(steps)))

    paths_html = (
        '  <section class="pop-sec reveal">\n'
        '    <div class="pop-head"><span class="pop-kicker">READING PATHS</span>'
        '<h2><span class="zh-only">三条阅读路线</span><span class="en-only">Three reading paths</span></h2>'
        '<p class="pop-sub"><span class="zh-only">不知道从哪篇开始？按处境选一条路走完。</span>'
        '<span class="en-only">Not sure where to start? Pick the path that matches your situation.</span></p></div>\n'
        '    <div class="path-grid">\n' + "\n".join(path_cards) + '\n    </div>\n  </section>')

    # ---- 最近更新 ----
    recent = []
    for a in arts[:6]:
        recent.append(
            '        <li><a href="%s"><span class="d">%s</span>'
            '<span class="t"><span class="zh-only">%s</span><span class="en-only">%s</span></span>'
            '<span class="c">%s</span></a></li>'
            % (a["file"], a["date"], esc_html(a["zh"]), esc_html(a["en"]), esc_html(a["cat"])))

    recent_html = (
        '  <section class="pop-sec reveal">\n'
        '    <div class="pop-head"><span class="pop-kicker">LATEST</span>'
        '<h2><span class="zh-only">最近更新</span><span class="en-only">Latest</span></h2></div>\n'
        '    <ul class="pop-recent">\n' + "\n".join(recent) + '\n    </ul>\n  </section>')

    return feat_html + "\n\n" + paths_html + "\n\n" + recent_html


# ==========================================================================
# 首页「内容索引」条
# ==========================================================================
def build_index_strip(arts, curated, tag_count):
    cats = curated.get("categories", {}) if isinstance(curated, dict) else {}
    n_cat = len(group_by_cat(arts))
    n_feat = len([f for f in curated.get("featured", []) if f.get("file") in {a["file"] for a in arts}])
    cards = [
        ("blog/", "ARCHIVE", "全部文章", "All articles", str(len(arts))),
        ("blog/categories.html", "CATEGORIES", "分类浏览", "Browse by category", str(n_cat)),
        ("blog/tags.html", "TAGS", "标签检索", "Search by tag", str(tag_count)),
        ("blog/popular.html", "FEATURED", "精选与路线", "Featured & paths", str(max(n_feat, 10))),
    ]
    rows = []
    for href, kicker, zh, en, n in cards:
        rows.append(
            '    <a href="%s" class="ix-card reveal">\n'
            '      <span class="ix-k">%s</span>\n'
            '      <span class="ix-t"><span class="zh-only">%s</span><span class="en-only">%s</span></span>\n'
            '      <span class="ix-n">%s</span>\n'
            '    </a>' % (href, kicker, zh, en, n))
    return "  <div class=\"index-strip\">\n" + "\n".join(rows) + "\n  </div>"


# ==========================================================================
# 通用页面装配：导航 / 页脚 / 主题 / PWA
# ==========================================================================
def blog_nav_html(active_key=""):
    items = []
    for key, href, zh, en in BLOG_NAV:
        cls = ' class="active"' if key == active_key else ''
        items.append(
            '<a href="%s" data-nav="%s"%s><span class="zh-only">%s</span>'
            '<span class="en-only">%s</span></a>' % (href, key, cls, zh, en))
    return "\n      ".join(items)


BLOG_FOOTER = """<footer class="blog-foot">
  <div class="bf-in">
    <nav class="bf-links" aria-label="Blog index / 文章索引">
      <a href="index.html"><span class="zh-only">文章归档</span><span class="en-only">Archive</span></a>
      <a href="categories.html"><span class="zh-only">分类</span><span class="en-only">Categories</span></a>
      <a href="tags.html"><span class="zh-only">标签</span><span class="en-only">Tags</span></a>
      <a href="popular.html"><span class="zh-only">精选</span><span class="en-only">Featured</span></a>
      <a href="../lab.html"><span class="zh-only">实验室</span><span class="en-only">Lab</span></a>
      <a href="../feed.xml">RSS</a>
    </nav>
    <p class="bf-copy">© 2026 Mu Chen · <span class="zh-only">木尘 · AI 编程实践者</span><span class="en-only">AI Coding Practitioner</span></p>
  </div>
</footer>"""

THEME_LINK = '<link rel="stylesheet" href="{base}assets/theme.css">'
MANIFEST_LINK = '<link rel="manifest" href="{base}manifest.json">'
APPLE_ICON = '<link rel="apple-touch-icon" href="{base}assets/apple-touch-icon.png">'
THEME_COLOR_META = '<meta name="theme-color" content="#0A0E1A">'
SW_REG = ("<script>if('serviceWorker' in navigator){window.addEventListener('load',function(){"
          "navigator.serviceWorker.register('/sw.js').catch(function(){})})}</script>")
THEME_JS = '<script src="{base}assets/theme.js"></script>'


def ensure_asset_links(path, base, page):
    """为页面补上 theme.css / blog-shell.css / taxonomy.css / manifest /
       apple-touch-icon / theme.js / sw 注册（幂等，重复运行不会叠加）"""
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return False
    s = open(p, encoding="utf-8").read()
    orig = s
    is_blog = page in ("index.html",) or path.startswith("blog/")

    def link_after(anchor, html_line, marker):
        nonlocal s
        if marker in s:
            return
        if anchor in s:
            s = s.replace(anchor, anchor + "\n" + html_line, 1)

    if is_blog:
        link_after('<link rel="stylesheet" href="blog.css">',
                   '<link rel="stylesheet" href="blog-shell.css">', "blog-shell.css")
        if page in ("categories.html", "tags.html", "popular.html"):
            link_after('<link rel="stylesheet" href="blog-shell.css">',
                       '<link rel="stylesheet" href="taxonomy.css">', "taxonomy.css")
        link_after('<link rel="stylesheet" href="blog.css">',
                   THEME_LINK.format(base=base), "assets/theme.css")
    else:
        link_after('<link rel="stylesheet" href="assets/site.css">',
                   THEME_LINK.format(base=base), "assets/theme.css")

    if "manifest.json" not in s:
        s = s.replace("</head>", MANIFEST_LINK.format(base=base) + "\n</head>", 1)
    if "apple-touch-icon" not in s:
        s = s.replace("</head>", APPLE_ICON.format(base=base) + "\n</head>", 1)
    if 'name="theme-color"' not in s:
        s = s.replace("</head>", THEME_COLOR_META + "\n</head>", 1)
    if "assets/theme.js" not in s:
        s = s.replace("</body>", THEME_JS.format(base=base) + "\n" + SW_REG + "\n</body>", 1)

    if s != orig:
        open(p, "w", encoding="utf-8").write(s)
        return True
    return False


def ensure_blog_nav(path, active_key):
    """把博客页的导航统一替换为归档/分类/标签/精选/实验室/关于"""
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return False
    s = open(p, encoding="utf-8").read()
    pat = re.compile(r'(<div class="nav-links" id="navlinks">)(.*?)(</div>)', re.S)
    m = pat.search(s)
    if not m:
        return False
    new = m.group(1) + "\n      " + blog_nav_html(active_key) + "\n    " + m.group(3)
    s = s[:m.start()] + new + s[m.end():]
    open(p, "w", encoding="utf-8").write(s)
    return True


def ensure_blog_footer(path):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return False
    s = open(p, encoding="utf-8").read()
    if 'class="blog-foot"' in s:
        return False
    m = re.search(r'<div class="foot-link">.*?</div>', s, re.S)
    if m:
        s = s[:m.end()] + "\n\n" + BLOG_FOOTER + s[m.end():]
    else:
        s = s.replace("</body>", BLOG_FOOTER + "\n</body>", 1)
    open(p, "w", encoding="utf-8").write(s)
    return True


def replace_block(path, marker, content):
    """把 <!-- MARKER --> ... <!-- /MARKER --> 之间的内容替换掉"""
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return False
    s = open(p, encoding="utf-8").read()
    pat = re.compile(r'(<!--\s*' + re.escape(marker) + r'\s*-->)(.*?)(<!--\s*/' + re.escape(marker) + r'\s*-->)',
                     re.S)
    m = pat.search(s)
    if not m:
        print(f"   ⚠️  {path}: 未找到标记 {marker}")
        return False
    s = s[:m.start(2)] + "\n" + content + "\n" + s[m.end(2):]
    open(p, "w", encoding="utf-8").write(s)
    return True


# ==========================================================================
# RSS / Sitemap
# ==========================================================================
def write_feed(arts):
    items = []
    for a in arts:
        link = f"{BASE}/blog/{a['file']}"
        cats = "".join(f"<category>{html.escape(t)}</category>" for t in a["tags"])
        items.append(
            f'    <item>\n      <title>{html.escape(a["zh"])}</title>\n      <link>{link}</link>\n'
            f'      <guid isPermaLink="true">{link}</guid>\n'
            f'      <pubDate>{a["date"].replace(".", "-")}</pubDate>\n'
            f'      <category>{html.escape(a["cat"])}</category>\n{cats}'
            f'      <description><![CDATA[{a["zh"]} — {a["en"]}]]></description>\n    </item>')
    today = datetime.date.today().isoformat()
    feed = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>木尘 · AI 编程实践者</title>
    <link>{BASE}/</link>
    <atom:link href="{BASE}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>AI 编程实践者，教普通人用 AI 做属于自己的产品。记录 AI 编程实战、独立开发复盘与普通人做出产品的完整路径。</description>
    <language>zh-CN</language>
    <copyright>© 2026 Mu Chen</copyright>
    <lastBuildDate>{today}T08:00:00+08:00</lastBuildDate>
    <generator>muchengit.github.io</generator>
{chr(10).join(items)}
  </channel>
</rss>
'''
    open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8").write(feed)


def write_sitemap(arts):
    today = datetime.date.today().isoformat()
    urls = [("", "1.0", "daily"), ("blog/", "0.9", "daily"),
            ("blog/categories.html", "0.8", "weekly"),
            ("blog/tags.html", "0.7", "weekly"),
            ("blog/popular.html", "0.8", "weekly"),
            ("lab.html", "0.6", "monthly"),
            ("projects/ai-study-buddy/", "0.5", "monthly"),
            ("projects/clipboard-ai/", "0.5", "monthly")]
    entries = []
    for path_, pri, freq in urls:
        loc = f"{BASE}/{path_}" if path_ else f"{BASE}/"
        entries.append(f'  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n'
                       f'    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>')
    for a in arts:
        entries.append(f'  <url>\n    <loc>{BASE}/blog/{a["file"]}</loc>\n'
                       f'    <lastmod>{a["date"].replace(".", "-")}</lastmod>\n'
                       f'    <changefreq>yearly</changefreq>\n    <priority>0.7</priority>\n  </url>')
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries) + "\n</urlset>\n")


# ==========================================================================
# 主流程
# ==========================================================================
def main():
    tagmap = load_json("tools/tagmap.json", {}) or {}
    curated = load_json("tools/curated.json", {}) or {}

    arts = collect(tagmap)
    total_words = sum(a["words"] for a in arts)
    read_min = max(1, round(total_words / 400))
    tagged = sum(1 for a in arts if a["tags"])
    tag_total = len(group_by_tag(arts))
    print(f"扫描到 {len(arts)} 篇文章，正文合计 {total_words:,} 字（约 {read_min} 分钟读完）；"
          f"已打标签 {tagged} 篇 / {tag_total} 个标签")

    write_articles_js(arts)

    # ---- 首页 ----
    p = os.path.join(ROOT, "index.html")
    s = open(p, encoding="utf-8").read()
    home_groups = build_home_groups(arts)
    pat_home = r'    <div class="post-group reveal">.*?(?=\n    <div class="more-wrap)'
    if not re.search(pat_home, s, flags=re.S):
        print("   ⚠️  index.html: 未找到文章区块")
    s = re.sub(pat_home, home_groups, s, flags=re.S)
    s = re.sub(r'(<div class="n">)\d+(</div>\s*<div class="l">\s*<span class="zh-only" data-i18n="stat_3">写的文章)',
               r'\g<1>%d\g<2>' % len(arts), s)
    s = re.sub(r'(查看全部 )\d+( 篇)', r'\g<1>%d\g<2>' % len(arts), s)
    s = re.sub(r'(Browse all )\d+( articles)', r'\g<1>%d\g<2>' % len(arts), s)
    open(p, "w", encoding="utf-8").write(s)
    replace_block("index.html", "SYNC:INDEX-STRIP", build_index_strip(arts, curated, tag_total))

    # ---- 归档页 ----
    p = os.path.join(ROOT, "blog/index.html")
    s = open(p, encoding="utf-8").read()
    arch_groups = build_archive_groups(arts)
    pat_arch = r'(  <div class="post-list" id="postList">\n).*?(?=\n  </div>\n)'
    if not re.search(pat_arch, s, flags=re.S):
        print("   ⚠️  blog/index.html: 未找到文章列表容器")
    s = re.sub(pat_arch, lambda m: m.group(1) + arch_groups + "\n", s, flags=re.S)
    s = re.sub(r'(<b id="statCount">)\d+(</b>)', r'\g<1>%d\g<2>' % len(arts), s)
    s = re.sub(r'(<b id="statWords">)[\d,]+(</b>)', r'\g<1>{:,}\g<2>'.format(total_words), s)
    s = re.sub(r'(<b id="statRead">)\d+(</b>)', r'\g<1>%d\g<2>' % read_min, s)
    s = re.sub(r'(<b id="cnt">)\d+(</b> / <b id="tot">)\d+(</b>)', r'\g<1>%d\g<2>%d\g<3>' % (len(arts), len(arts)), s)
    s = re.sub(r'(<b id="cnt-en">)\d+(</b> / <b id="tot-en">)\d+(</b>)', r'\g<1>%d\g<2>%d\g<3>' % (len(arts), len(arts)), s)
    s = re.sub(r'(\d+ 篇 AI 编程实战文章)', r'%d 篇 AI 编程实战文章' % len(arts), s)
    s = re.sub(r'(\d+ hands-on AI coding articles)', r'%d hands-on AI coding articles' % len(arts), s)
    s = re.sub(r'(归档：)\d+( 篇文章)', r'\g<1>%d\g<2>' % len(arts), s)
    s = re.sub(r'(Archive of )\d+( hands-on)', r'\g<1>%d\g<2>' % len(arts), s)
    open(p, "w", encoding="utf-8").write(s)

    # ---- 分类 / 标签 / 精选页 ----
    replace_block("blog/categories.html", "SYNC:CATEGORIES", build_categories_html(arts, curated))
    replace_block("blog/tags.html", "SYNC:TAGS", build_tags_html(arts))
    replace_block("blog/popular.html", "SYNC:POPULAR", build_popular_html(arts, curated))

    # ---- 新页面顶部统计数字 ----
    n_cat = len(group_by_cat(arts))
    n_tagged = sum(1 for a in arts if a["tags"])
    n_feat = len([f for f in curated.get("featured", []) if f.get("file") in {a["file"] for a in arts}])
    n_paths = len(curated.get("paths", []))
    stats = {
        "blog/categories.html": {"statCats": n_cat, "statArts": len(arts),
                                 "statWords": "{:,}".format(total_words)},
        "blog/tags.html": {"statTags": tag_total, "statTagged": n_tagged},
        "blog/popular.html": {"statFeat": max(n_feat, 10), "statPaths": n_paths},
    }
    for path_, kv in stats.items():
        full = os.path.join(ROOT, path_)
        if not os.path.exists(full):
            continue
        src = open(full, encoding="utf-8").read()
        for k, v in kv.items():
            src = re.sub(r'(<b id="%s">)[^<]*(</b>)' % re.escape(k), r'\g<1>%s\g<2>' % v, src)
        open(full, "w", encoding="utf-8").write(src)

    # ---- 导航 / 页脚 / 主题资源 ----
    blog_pages = sorted(glob.glob(os.path.join(BLOG, "*.html")))
    for path in blog_pages:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        base = os.path.basename(path)
        active = {"index.html": "archive", "categories.html": "categories",
                  "tags.html": "tags", "popular.html": "popular"}.get(base, "")
        ensure_asset_links(rel, "../", base)
        ensure_blog_nav(rel, active)
        ensure_blog_footer(rel)
    for rel in ("index.html", "lab.html"):
        ensure_asset_links(rel, "", rel)

    # ---- RSS / Sitemap ----
    write_feed(arts)
    write_sitemap(arts)

    print("✅ 已同步：articles.js / index.html / blog/（归档·分类·标签·精选）"
          " / feed.xml / sitemap.xml / 导航 / 页脚 / 主题")
    print(f"   文章 {len(arts)} 篇 · 合计 {total_words:,} 字 · 约 {read_min} 分钟 · "
          f"分类 {len(group_by_cat(arts))} 个 · 标签 {tag_total} 个")


if __name__ == "__main__":
    main()
