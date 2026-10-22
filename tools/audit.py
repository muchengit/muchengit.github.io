#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站体检：结构合法性 / 内部链接 / 资源引用 / 双语配对 / 清单一致性"""
import re, os, sys, glob, html.parser
from urllib.parse import urlparse, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "lab.html", "blog/index.html"] + sorted(
    p for p in glob.glob(os.path.join(ROOT, "blog/*.html")) if not p.endswith("/index.html")
)

VOID = {"meta", "link", "img", "br", "hr", "input", "source", "wbr", "path", "circle", "rect", "polygon", "use", "stop", "area", "base", "col", "embed", "track", "param"}


class P(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errs = [], []
    def handle_starttag(self, t, a):
        if t not in VOID:
            self.stack.append((t, self.getpos()))
    def handle_endtag(self, t):
        if not self.stack:
            self.errs.append(f"多余的 </{t}> @ {self.getpos()}"); return
        if self.stack[-1][0] == t:
            self.stack.pop(); return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == t:
                for j in range(len(self.stack) - 1, i - 1, -1):
                    self.errs.append(f"未闭合 <{self.stack[j][0]}> @ {self.stack[j][1]}")
                del self.stack[i:]; return
        self.errs.append(f"孤立 </{t}> @ {self.getpos()}")


problems = []
print("=" * 74)
print("1. HTML 结构合法性")
print("=" * 74)
for rel in PAGES:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print(f"  ⚠️  文件不存在: {rel}"); continue
    src = open(p, encoding="utf-8").read()
    parser = P(); parser.feed(src)
    errs = parser.errs + [f"未闭合 <{t}> @ {pos}" for t, pos in parser.stack]
    if errs:
        problems.append((rel, errs))
        print(f"  ❌ {rel}")
        for e in errs[:5]: print(f"       {e}")
    else:
        print(f"  ✅ {rel}  ({len(src)//1024}KB)")

print()
print("=" * 74)
print("2. 内部链接与资源引用")
print("=" * 74)
missing = 0
for rel in PAGES:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p): continue
    src = open(p, encoding="utf-8").read()
    base = os.path.dirname(p)
    refs = []
    refs += [("href", m) for m in re.findall(r'<a[^>]+href="([^"]+)"', src)]
    refs += [("src", m) for m in re.findall(r'<img[^>]+src="([^"]+)"', src)]
    refs += [("link", m) for m in re.findall(r'<link[^>]+href="([^"]+)"', src)]
    refs += [("script", m) for m in re.findall(r'<script[^>]+src="([^"]+)"', src)]
    bad = []
    for kind, r in refs:
        if r.startswith(("http://", "https://", "mailto:", "#", "data:", "javascript:")):
            continue
        target = unquote(r.split("#")[0].split("?")[0])
        if not target:
            continue
        full = os.path.normpath(os.path.join(base, target))
        if os.path.exists(full):
            continue
        # 目录链接 → 补 index.html
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "index.html")):
            continue
        bad.append(f"{kind}={r}")
    if bad:
        missing += len(bad)
        problems.append((rel, bad))
        print(f"  ❌ {rel}")
        for b in bad[:8]: print(f"       找不到 → {b}")
    else:
        print(f"  ✅ {rel}  所有内部链接/资源均可解析")
print(f"\n  共 {missing} 个失效引用")

print()
print("=" * 74)
print("3. 新文章双语配对（仅供参考）")
print("=" * 74)
print("  注：分类标签的写法各篇不一（中文可能不在 zh-only 内），计数天然不相等，")
print("      不能作为判定依据。真正的正确性由 check_i18n.py 的「英文模式残留检查」验证。")
for rel in sorted(glob.glob(os.path.join(ROOT, "blog/2026-*.html"))):
    src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    zh = len(re.findall(r'class="zh-only"', src))
    en = len(re.findall(r'class="en-only"', src))
    sections = len(re.findall(r'<section class="prose', src))
    print(f"  · {os.path.basename(rel):<42} zh-only={zh:<4} en-only={en:<4} 小节数={sections}")

print()
print("=" * 74)
print("4. 文章清单一致性 (blog/articles.js vs 实际文件)")
print("=" * 74)
man = open(os.path.join(ROOT, "blog/articles.js"), encoding="utf-8").read()
listed = re.findall(r'\{file:"([^"]+)"', man)
actual = sorted(os.path.basename(f) for f in glob.glob(os.path.join(ROOT, "blog/*.html"))
                 if not f.endswith("/index.html"))
only_list = [f for f in listed if f not in actual]
only_disk = [f for f in actual if f not in listed]
print(f"  清单条目: {len(listed)}   磁盘文章: {len(actual)}")
if only_list:
    problems.append(("articles.js", [f"清单有但磁盘无: {only_list}"]))
    print(f"  ❌ 清单中不存在的文件: {only_list}")
if only_disk:
    problems.append(("articles.js", [f"磁盘有但清单无: {only_disk}"]))
    print(f"  ❌ 未登记的文章: {only_disk}")
if not only_list and not only_disk:
    print("  ✅ 完全一致")

print()
print("=" * 74)
if problems:
    print(f"❌ 共发现 {len(problems)} 处问题")
    for r, e in problems: print(f"   {r}: {e[:3]}")
    sys.exit(1)
print("✅ 全站体检通过，0 问题")
