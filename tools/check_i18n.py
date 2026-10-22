#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟英文模式：移除 zh-only 包裹的内容后，检查可见文本里是否还有中文残留"""
import re, os, glob, sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CJK = re.compile(r'[\u4e00-\u9fa5\u3040-\u30ff]')

# 这些区域允许出现中文（品牌名 / 代码示例 / 路径 / 中文专有名词白名单）
WHITELIST = [
    "木尘", "不服输的老码农", "文章", "实验室", "作品", "关于", "联系", "返回",
    "目录", "回到主页", "复制", "跳过主要内容",
    "EN / 中", "中 / EN",  # 语言切换按钮本身是双语标签，属预期
]


class Extract(HTMLParser):
    """收集 en 模式下可见的文本（跳过 zh-only 子树、script/style）"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.skip_tags = 0
        self.texts = []
        self.title = None
        self._in_title = False

    def handle_starttag(self, t, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if t in ("script", "style"):
            self.skip_tags += 1
        if "zh-only" in cls.split():
            self.skip_depth += 1
        if t == "title":
            self._in_title = True

    def handle_endtag(self, t):
        if t in ("script", "style") and self.skip_tags:
            self.skip_tags -= 1
        if t == "title":
            self._in_title = False

    def handle_data(self, data):
        if self.skip_depth or self.skip_tags:
            return
        s = data.strip()
        if not s:
            return
        if self._in_title:
            self.title = s
        else:
            self.texts.append(s)


def check(path):
    src = open(path, encoding="utf-8").read()
    p = Extract()
    p.feed(src)
    leftover = []
    for t in p.texts:
        if CJK.search(t):
            # 逐个检查是否命中白名单词
            hit = None
            for w in WHITELIST:
                if w in t:
                    # 去掉白名单词后如果不再有中文，视为通过
                    rest = CJK.sub("", t.replace(w, ""))
                    if not rest.strip():
                        continue
            if hit is None and not all(CJK.sub("", t.replace(w, "")) is None for w in WHITELIST):
                # 逐白名单词剔除后再判断
                rest = t
                for w in WHITELIST:
                    rest = rest.replace(w, "")
                if CJK.search(rest):
                    leftover.append((t[:70], CJK.findall(rest)[:8]))
    return p.title, leftover


print("=" * 76)
print("英文模式残留中文检查（模拟移除 zh-only 后，可见文本中不应再有中文）")
print("=" * 76)

files = ["index.html", "lab.html", "blog/index.html"] + sorted(
    os.path.relpath(f, ROOT).replace(os.sep, "/")
    for f in glob.glob(os.path.join(ROOT, "blog/*.html"))
    if not f.endswith("/index.html")
)

total_bad = 0
for rel in files:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    title, leftover = check(p)
    if leftover:
        total_bad += len(leftover)
        print(f"  ❌ {rel}  ({len(leftover)} 处)")
        for t, chars in leftover[:4]:
            print(f"       「{t}」 残留字符: {''.join(chars)}")
    else:
        print(f"  ✅ {rel}")

print()
if total_bad:
    print(f"❌ 共 {total_bad} 处英文模式中文残留")
    sys.exit(1)
print("✅ 全部页面英文模式无中文残留")
