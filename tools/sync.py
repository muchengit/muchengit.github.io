#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.py — 站点内容同步器
扫描 blog/ 下的文章文件，自动重建：
  1. blog/articles.js   文章清单（日期倒序，含字数）
  2. index.html        首页「文章」板块（按年份分组）
  3. blog/index.html   文章归档页（按年份分组的静态列表）
  4. feed.xml          RSS 订阅源
  5. sitemap.xml       站点地图

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


def strip_tags(s):
    s = re.sub(r'<span class="en-only">.*?</span>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def parse_article(path):
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

    # 中文字数（去掉英文分支）
    z = re.sub(r'<span class="en-only">.*?</span>', '', src, flags=re.S)
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
        desc_en = desc_en[:110].rstrip("，,、 ") + "…"

    return dict(file=name, date=date, cat=cat, catEn=cat_en, zh=zh, en=en,
                words=words, descZh=desc_zh, descEn=desc_en)


def collect():
    arts = []
    for p in sorted(glob.glob(os.path.join(BLOG, "*.html"))):
        if os.path.basename(p) == "index.html":
            continue
        arts.append(parse_article(p))
    arts.sort(key=lambda a: (a["date"], a["file"]), reverse=True)
    return arts


def write_articles_js(arts):
    lines = ["/* 文章清单 — 供 blog.js 与 tools/sync.py 使用",
             "   字段：file 文件名, date 发布日期, cat 分类, catEn 分类英文, words 正文字数, zh 中文标题, en 英文标题",
             "   本文件由 tools/sync.py 自动生成，请勿手工编辑 */",
             "window.SITE_ARTICLES = ["]
    for a in arts:
        lines.append(
            '  {file:"%s", date:"%s", cat:"%s", catEn:"%s", words:%d, zh:"%s", en:"%s"},'
            % (a["file"], a["date"], a["cat"], a["catEn"], a["words"],
               a["zh"].replace('"', '\\"'), a["en"].replace('"', '\\"')))
    lines.append("];")
    open(os.path.join(BLOG, "articles.js"), "w", encoding="utf-8").write("\n".join(lines))


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
                % (a["file"], a["date"], a["zh"], a["en"], a["descZh"], a["descEn"], a["cat"], a["catEn"]))
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
                '        <a class="post" href="%s" data-year="%s" data-cat="%s" data-cat-en="%s">\n'
                '          <span class="post-date">%s</span>\n'
                '          <h3 class="post-title"><span class="zh-only">%s</span><span class="en-only">%s</span></h3>\n'
                '          <span class="post-cat"><span class="zh-only">%s</span><span class="en-only">%s</span></span>\n'
                '          <p class="post-desc"><span class="zh-only">%s</span><span class="en-only">%s</span></p>\n'
                '          <span class="post-arrow" aria-hidden="true">&rarr;</span>\n'
                '        </a>'
                % (a["file"], year, a["cat"], a["catEn"], a["date"], a["zh"], a["en"],
                   a["cat"], a["catEn"], a["descZh"], a["descEn"]))
        groups.append(
            '    <section class="ygroup" data-year="%s">\n'
            '      <h2 class="yhead"><span class="yyear">%s</span><span class="yn">'
            '<span class="zh-only">共 <b class="yn-count">%d</b> 篇</span>'
            '<span class="en-only"><b class="yn-count">%d</b> articles</span></span></h2>\n'
            '      <div class="posts">\n%s\n      </div>\n    </section>'
            % (year, year, len(items), len(items), "\n".join(rows)))
    return "\n".join(groups)


def patch(path, pairs):
    p = os.path.join(ROOT, path)
    s = open(p, encoding="utf-8").read()
    for pat, rep in pairs:
        new, n = re.subn(pat, rep, s, flags=re.S)
        if n == 0:
            print(f"   ⚠️  {path}: 未匹配到 {pat[:48]!r}")
        s = new
    open(p, "w", encoding="utf-8").write(s)


def main():
    arts = collect()
    total_words = sum(a["words"] for a in arts)
    read_min = max(1, round(total_words / 400))
    print(f"扫描到 {len(arts)} 篇文章，正文合计 {total_words:,} 字（约 {read_min} 分钟读完）")

    write_articles_js(arts)

    # ---- 首页 ----
    home_groups = build_home_groups(arts)
    patch("index.html", [
        (r'(    <div class="post-group reveal">\n      <div class="post-year">2026</div>.*?\n    </div>\n\n)(?=\s*<div class="more-wrap)',
         lambda m: m.group(1)),
    ]) if False else None
    p = os.path.join(ROOT, "index.html")
    s = open(p, encoding="utf-8").read()
    s2 = re.sub(r'    <div class="post-group reveal">.*?(?=\n    <div class="more-wrap)', home_groups, s, flags=re.S)
    if s2 == s:
        print("   ⚠️  index.html: 文章区块未替换")
    s = s2
    s = re.sub(r'(<div class="n">)\d+(</div>\s*<div class="l">\s*<span class="zh-only" data-i18n="stat_3">写的文章)',
               r'\g<1>%d\g<2>' % len(arts), s)
    s = re.sub(r'(查看全部 )\d+( 篇)', r'\g<1>%d\g<2>' % len(arts), s)
    s = re.sub(r'(Browse all )\d+( articles)', r'\g<1>%d\g<2>' % len(arts), s)
    open(p, "w", encoding="utf-8").write(s)

    # ---- 归档页 ----
    arch_groups = build_archive_groups(arts)
    p = os.path.join(ROOT, "blog/index.html")
    s = open(p, encoding="utf-8").read()
    s2 = re.sub(r'(  <div class="post-list" id="postList">\n).*?(?=\n  </div>\n)',
                lambda m: m.group(1) + arch_groups + "\n", s, flags=re.S)
    if s2 == s:
        print("   ⚠️  blog/index.html: 年份分组未替换")
    s = s2
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

    # ---- RSS ----
    def esc(x):
        return html.escape(x, quote=True)
    items = []
    for a in arts:
        link = f"{BASE}/blog/{a['file']}"
        items.append(
            f'    <item>\n      <title>{esc(a["zh"])}</title>\n      <link>{link}</link>\n'
            f'      <guid isPermaLink="true">{link}</guid>\n'
            f'      <pubDate>{a["date"].replace(".", "-")}</pubDate>\n'
            f'      <category>{esc(a["cat"])}</category>\n'
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

    # ---- sitemap ----
    urls = [("", "1.0", "daily"), ("blog/", "0.9", "weekly"), ("lab.html", "0.6", "monthly"),
            ("projects/ai-study-buddy/", "0.5", "monthly"), ("projects/clipboard-ai/", "0.5", "monthly")]
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

    print(f"✅ 已同步：articles.js / index.html / blog/index.html / feed.xml / sitemap.xml")
    print(f"   文章 {len(arts)} 篇 · 合计 {total_words:,} 字 · 约 {read_min} 分钟")


if __name__ == "__main__":
    main()
