#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从旧站静态 HTML 快照反提取文章，还原成 Hexo 的 Markdown 源码。

用法：
    python tools/restore_snapshot.py              # 只还原文章
    python tools/restore_snapshot.py --assets     # 同时复制旧站静态资源
    python tools/restore_snapshot.py --force      # 覆盖已存在的 md

设计原则：
  1. 每篇文章显式写 permalink，锁定 2015 年就存在的老 URL，绝不改变；
  2. 保留原始发布时间、分类、标签；
  3. 正文由 HTML 转成 Markdown，方便以后继续编辑；
  4. 图片链接原样保留（很多是失效的第三方外链），并在报告里逐条列出。
"""

import argparse
import html
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "_work" / "snapshot" / "hnustluyu.github.io-master"
POSTS_DIR = ROOT / "source" / "_posts"
SOURCE_DIR = ROOT / "source"
REPORT = ROOT / "_work" / "restore-report.md"

POST_PATH_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})/(.+)/index\.html$")
DIV_TAG_RE = re.compile(r"<(/?)div\b[^>]*>", re.I)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
ATTR_RE = re.compile(r"([\w:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))")


def unescape(s):
    return html.unescape(s or "").replace("\u00a0", " ").strip()


def meta(content, key):
    for pattern in (
        r'<meta\s+property="%s"\s+content="([^"]*)"',
        r'<meta\s+name="%s"\s+content="([^"]*)"',
    ):
        m = re.search(pattern % re.escape(key), content, re.I)
        if m:
            return unescape(m.group(1))
    return ""


def inner_html_of_div(content, marker_regex):
    """找到匹配 marker 的 div，返回其内部 HTML（按 div 嵌套计数）。"""
    m = re.search(marker_regex, content, re.I)
    if not m:
        return ""
    gt = content.find(">", m.start())
    if gt < 0:
        return ""
    i, depth = gt + 1, 1
    while depth > 0:
        t = DIV_TAG_RE.search(content, i)
        if not t:
            break
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return content[gt + 1 : t.start()]
        i = t.end()
    return content[gt + 1 :]


def strip_tags(s):
    return unescape(re.sub(r"<[^>]+>", "", s))


def html_to_markdown(fragment):
    """把旧站 article-entry 的简单 HTML 转成可读的 Markdown。"""
    s = fragment
    # 图片：优先 src，其次 data-src / lazy-src / data-original
    def img_repl(m):
        tag = m.group(0)
        attrs = {}
        for a in ATTR_RE.finditer(tag):
            attrs[a.group(1).lower()] = a.group(2) or a.group(3) or a.group(4) or ""
        src = (attrs.get("src") or attrs.get("data-src") or attrs.get("lazy-src")
               or attrs.get("data-original") or "")
        if src.startswith("//"):
            src = "https:" + src
        alt = attrs.get("alt", "").replace("]", "")
        return "\n\n![%s](%s)\n\n" % (alt, src) if src else ""

    s = IMG_RE.sub(img_repl, s)
    s = re.sub(r"<a\b[^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
               lambda m: "[%s](%s)" % (strip_tags(m.group(2)), m.group(1)), s, flags=re.I | re.S)
    s = re.sub(r"<br\s*/?>", "  \n", s, flags=re.I)
    s = re.sub(r"<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", s, flags=re.I | re.S)
    s = re.sub(r"<(em|i)\b[^>]*>(.*?)</\1>", r"*\2*", s, flags=re.I | re.S)
    s = re.sub(r"<h([1-6])\b[^>]*>(.*?)</h\1>",
               lambda m: "\n\n" + "#" * int(m.group(1)) + " " + strip_tags(m.group(2)) + "\n\n",
               s, flags=re.I | re.S)
    s = re.sub(r"<blockquote\b[^>]*>(.*?)</blockquote>",
               lambda m: "\n\n" + "\n".join("> " + x for x in strip_tags(m.group(1)).splitlines()) + "\n\n",
               s, flags=re.I | re.S)
    s = re.sub(r"</p\s*>", "\n\n", s, flags=re.I)
    s = re.sub(r"<p\b[^>]*>", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)                      # 其余标签一律去掉
    s = unescape(s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def yaml_str(v):
    return "'" + str(v).replace("'", "''") + "'"


def safe_filename(title):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "-", title).strip()
    return name[:80] or "untitled"


def collect_assets():
    copied = []
    for sub in ("css", "js", "fancybox", "img", "uploads"):
        src = SNAPSHOT / sub
        if not src.is_dir():
            continue
        dst = SOURCE_DIR / sub
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        copied.append("%s (%d files)" % (sub, sum(1 for _ in dst.rglob("*") if _.is_file())))
    fav = SNAPSHOT / "img" / "favicon.png"
    if fav.exists():
        shutil.copy2(fav, SOURCE_DIR / "favicon.png")   # 旧站 /favicon.png 原本是 404，顺手补上
        copied.append("favicon.png")
    return copied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", action="store_true", help="同时复制旧站静态资源")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 Markdown")
    args = ap.parse_args()

    if not SNAPSHOT.is_dir():
        raise SystemExit("找不到旧站快照：%s" % SNAPSHOT)

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    found = []
    for f in sorted(SNAPSHOT.rglob("index.html")):
        rel = f.relative_to(SNAPSHOT).as_posix()
        m = POST_PATH_RE.match(rel)
        if m:
            found.append((f, m))

    if not found:
        raise SystemExit("快照里没有找到形如 YYYY/MM/DD/标题/index.html 的文章页")

    rows = []
    for f, m in found:
        y, mo, d, raw_title = m.groups()
        content = f.read_text(encoding="utf-8", errors="replace")
        title = meta(content, "og:title") or unescape(raw_title)
        tm = re.search(r'<time[^>]*datetime="([^"]+)"', content)
        raw_iso = tm.group(1) if tm else ""
        # 旧站 datetime 是 UTC（带 Z）。新版 Hexo 会把带 Z 的字符串按本地时区
        # 解析，导致部分文章在归档页显示成前一天。这里统一转成不带时区的
        # 北京时间字符串，并强制显示日期 == URL 里的日期。
        path_day = "%s-%s-%s" % (y, mo, d)
        try:
            utc_dt = datetime.fromisoformat(raw_iso.replace("Z", "+00:00"))
            local = utc_dt.astimezone(timezone(timedelta(hours=8)))
            if local.strftime("%Y-%m-%d") != path_day:
                date = path_day + " 12:00:00"
            else:
                date = local.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            date = path_day + " 12:00:00"
        cat_m = re.search(r'class="article-category-link"[^>]*>(.*?)</a>', content, re.I | re.S)
        category = strip_tags(cat_m.group(1)) if cat_m else ""
        tag_box = inner_html_of_div(content, r'<div class="article-tag tagcloud"')
        tags = [strip_tags(x) for x in re.findall(r"<a\b[^>]*>(.*?)</a>", tag_box, re.I | re.S)]
        tags = [t for t in tags if t]
        body_html = inner_html_of_div(content, r'<div class="article-entry"\s+itemprop="articleBody"')
        body = html_to_markdown(body_html)
        permalink = "/%s/%s/%s/%s/" % (y, mo, d, raw_title)
        images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body)

        fm = ["---",
              "title: %s" % yaml_str(title),
              "date: %s" % date,
              "categories: %s" % (yaml_str(category) if category else "[]"),
              "tags: [%s]" % ", ".join(yaml_str(t) for t in tags),
              "permalink: %s" % yaml_str(permalink),
              "origin: %s" % yaml_str("旧站 westbar.cn 静态页反提取（原文来自新浪博客）"),
              "---", ""]
        md = "\n".join(fm) + body + "\n"
        out = POSTS_DIR / ("%s-%s-%s-%s.md" % (y, mo, d, safe_filename(title)))
        existed = out.exists()
        if not existed or args.force:
            out.write_text(md, encoding="utf-8")
        rows.append((title, date[:10], permalink, out.name,
                     "覆盖" if existed and args.force else ("跳过(已存在)" if existed else "新建"),
                     len(images), images))

    assets = collect_assets() if args.assets else []

    lines = ["# 旧站文章反提取报告", "",
             "快照目录：`%s`" % SNAPSHOT.as_posix(),
             "共发现 %d 篇文章，输出目录：`source/_posts/`" % len(rows), ""]
    if assets:
        lines += ["## 已复制的静态资源", ""] + ["- " + a for a in assets] + [""]
    lines += ["## 文章清单", "",
              "| 标题 | 日期 | 固定链接 | 文件 | 状态 | 图片数 |",
              "| --- | --- | --- | --- | --- | --- |"]
    for t, d, p, fn, st, n, _ in rows:
        lines.append("| %s | %s | `%s` | `%s` | %s | %d |" %
                     (t.replace("|", "\\|"), d, p, fn, st, n))
    allimgs = [(t, u) for t, d, p, fn, st, n, imgs in rows for u in imgs]
    if allimgs:
        lines += ["", "## 图片链接（请逐条确认是否还有效）", ""]
        for t, u in allimgs:
            lines.append("- **%s** → `%s`" % (t, u))
        lines += ["", "> 外链图片多为早期图床，若已失效，可把图片放到 "
                  "`source/images/` 后把链接改成 `/images/xxx.jpg`。", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("还原 %d 篇文章 -> %s" % (len(rows), POSTS_DIR))
    for t, d, p, fn, st, n, _ in rows:
        print("  [%s] %s  %s" % (st, d, t))
    print("报告：%s" % REPORT)


if __name__ == "__main__":
    main()
