#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新浪博客导出文件 -> Hexo Markdown 通用导入器

用法：
    python tools/import_sina.py                      # 导入 import/ 目录下所有可识别文件
    python tools/import_sina.py --dry-run           # 只预览，不写文件
    python tools/import_sina.py --download-images   # 同时把外链图片下载到本地
    python tools/import_sina.py --dir D:/下载/备份   # 指定其它目录
    python tools/import_sina.py --keep-duplicates   # 不跳过与现有文章同名的条目

支持来源（自动识别）：
    * 新浪博客后台「文章导出」：.xlsx / .xls(实为csv) / .csv
    * dature / BlogDown / 网页另存为：.html / .htm
    * 已经整理好的：.md / .markdown / .txt
    * BlogDown 等：.xml / .json / .ndjson

产出：
    source/_posts/YYYY-MM-DD-标题.md  （带完整 front-matter）
    import/import-report.md          （逐篇核对报告）
"""

import argparse
import csv
import hashlib
import html as html_lib
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from restore_snapshot import (  # noqa: E402
    html_to_markdown, inner_html_of_div, strip_tags, yaml_str, safe_filename, unescape,
)

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "source" / "_posts"
IMG_DIR = ROOT / "source" / "images" / "sina"
DEFAULT_INPUT = ROOT / "import"
REPORT = ROOT / "import" / "import-report.md"

SUPPORTED = {".xlsx", ".xls", ".csv", ".tsv", ".html", ".htm", ".md", ".markdown",
             ".txt", ".xml", ".json", ".ndjson"}

# 新浪官方「文章导出」只有 时间/标题/内容 三列，缺分类和标签，这里给默认值
FALLBACK_CATEGORY = "随笔"
FALLBACK_TAGS = ["新浪博客"]

DATE_RE = re.compile(
    r"(?:19|20)\d{2}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}日?"
    r"(?:[\sT]+\d{1,2}:\d{2}(?::\d{2})?)?"
)
IMG_URL_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------
def yaml_front(title, dt, category, tags, source_url, permalink=None):
    lines = ["---", "title: %s" % yaml_str(title),
             "date: %s" % dt,
             "categories: %s" % (yaml_str(category) if category else "[]"),
             "tags: [%s]" % ", ".join(yaml_str(t) for t in tags),
             "origin: %s" % yaml_str("新浪博客 (blog.sina.com.cn/u/1389586804)")]
    if source_url:
        lines.append("source_url: %s" % yaml_str(source_url))
    if permalink:
        lines.append("permalink: %s" % yaml_str(permalink))
    lines += ["---", ""]
    return "\n".join(lines)


def normalize_date(raw, fallback=None):
    """返回 (YYYY-MM-DD, 'YYYY-MM-DD HH:MM:SS')；识别不到日期时返回 fallback。"""
    if raw:
        s = str(raw).strip()
        # Excel 序列号
        if re.fullmatch(r"\d{5}(\.\d+)?", s):
            try:
                d = date(1899, 12, 30).fromordinal(
                    date(1899, 12, 30).toordinal() + int(float(s)))
                return d.isoformat(), d.isoformat() + " 00:00:00"
            except Exception:
                pass
        m = DATE_RE.search(s)
        if m:
            nums = re.findall(r"\d+", m.group(0))
            y, mo, d = int(nums[0]), int(nums[1]), int(nums[2])
            hh, mm, ss = (int(nums[3]) if len(nums) > 3 else 0,
                          int(nums[4]) if len(nums) > 4 else 0,
                          int(nums[5]) if len(nums) > 5 else 0)
            try:
                d0 = date(y, mo, d)
                return d0.isoformat(), "%s %02d:%02d:%02d" % (d0.isoformat(), hh, mm, ss)
            except ValueError:
                pass
    if fallback:
        return fallback
    today = date.today().isoformat()
    return today, today + " 00:00:00"


def guess_fields(row):
    """从表头行猜测列位置。返回 {字段: 列索引}。"""
    keys = {
        "title": ("标题", "题目", "博文标题", "title", "subject", "name"),
        "date": ("时间", "日期", "发表时间", "发布时间", "创建时间", "date", "time", "pubdate"),
        "body": ("正文", "内容", "文章内容", "博文内容", "content", "body", "text"),
        "category": ("分类", "栏目", "类别", "category", "categories"),
        "tags": ("标签", "关键字", "tag", "tags", "keyword"),
        "url": ("链接", "地址", "原文", "原文链接", "url", "link"),
    }
    out = {}
    for idx, cell in enumerate(row):
        c = unescape(str(cell)).lower().replace(" ", "")
        for field, aliases in keys.items():
            if field in out:
                continue
            if any(a in c for a in aliases):
                out[field] = idx
    return out


def pick(row, fields, key, default=""):
    i = fields.get(key)
    if i is None or i >= len(row):
        return default
    return unescape(str(row[i] or ""))


# --------------------------------------------------------------------------
# 各种格式解析 -> 统一的 dict 列表
# --------------------------------------------------------------------------
def parse_xlsx(path):
    """用标准库解析 xlsx，不依赖 openpyxl。"""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            x = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            for si in re.findall(r"<si>(.*?)</si>", x, re.S):
                shared.append(html_lib.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
        names = [n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
        if not names:
            return []
        sheet = z.read(sorted(names)[0]).decode("utf-8", "replace")
        rows = []
        for rm in re.finditer(r"<row\b[^>]*>(.*?)</row>", sheet, re.S):
            cells = {}
            for cm in re.finditer(r"<c\b([^>]*)>(.*?)</c>|<c\b([^>]*)/>", rm.group(1), re.S):
                attrs = cm.group(1) or cm.group(3) or ""
                body = cm.group(2) or ""
                ref = re.search(r'r="([A-Z]+)\d+"', attrs)
                col = 0
                if ref:
                    for ch in ref.group(1):
                        col = col * 26 + (ord(ch) - 64)
                    col -= 1
                else:
                    col = len(cells)
                t = re.search(r't="([^"]+)"', attrs)
                typ = t.group(1) if t else ""
                if typ == "s":
                    v = re.search(r"<v>(.*?)</v>", body, re.S)
                    val = shared[int(v.group(1))] if v and v.group(1).isdigit() and int(v.group(1)) < len(shared) else ""
                elif typ == "inlineStr":
                    val = html_lib.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", body, re.S)))
                else:
                    v = re.search(r"<v>(.*?)</v>", body, re.S)
                    val = html_lib.unescape(v.group(1)) if v else ""
                cells[col] = val
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
    return rows_to_items(rows, str(path))


def clean_plain_body(s):
    """新浪官方导出的正文是纯文本 + HTML 实体；把连续 &nbsp; 还原成段落分隔。"""
    s = s.replace("&#65279;", "").replace("\ufeff", "").replace("\u200b", "")
    s = html_lib.unescape(s).replace("\u00a0", " ")
    s = re.sub(r"[ \t]{2,}", "\n\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_delimited(path, raw=None):
    """Tab / 逗号分隔的纯文本表格（新浪导出的 .xls 其实就是 GBK 编码的 TSV）。"""
    raw = raw if raw is not None else path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-16", "gb18030", "gbk", "big5"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("gb18030", "replace")
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines:
        return []
    counts = {d: lines[0].count(d) for d in "\t,;|"}
    delim = max(counts, key=lambda k: counts[k])
    if counts[delim] == 0:
        delim = "\t" if "\t" in text[:4096] else ","
    rows = list(csv.reader(lines, delimiter=delim))
    return rows_to_items(rows, str(path))


def parse_html_table(path):
    """有些系统导出的 .xls 实际是 HTML 表格。"""
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "gb18030", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    text = text or raw.decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, re.I | re.S):
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", tr, re.I | re.S)
        rows.append([strip_tags(c) for c in cells])
    return rows_to_items(rows, str(path))


def parse_table_file(path):
    """按文件头判断真实格式：xlsx / OLE2 二进制 xls / HTML 表格 / 分隔文本。"""
    raw = path.read_bytes()
    if raw[:2] == b"PK":
        return parse_xlsx(path)
    if raw[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("这是二进制 .xls，请先用 Excel 另存为 .xlsx 或 CSV 再导入")
    head = raw[:4096].decode("gb18030", "replace").lower()
    if "<table" in head or "<html" in head:
        return parse_html_table(path)
    return parse_delimited(path, raw)


def parse_csv(path):
    return parse_delimited(path)


def rows_to_items(rows, src):
    if not rows:
        return []
    fields = guess_fields(rows[0])
    has_header = "title" in fields or "body" in fields
    start = 1 if has_header else 0
    items = []
    for row in rows[start:]:
        if not any(unescape(str(c)).strip() for c in row):
            continue
        if has_header:
            raw_body = pick(row, fields, "body")
            item = {
                "title": pick(row, fields, "title"),
                "date_raw": pick(row, fields, "date"),
                "category": pick(row, fields, "category"),
                "tags": [t.strip() for t in re.split(r"[,，;；|/]", pick(row, fields, "tags")) if t.strip()],
                "url": pick(row, fields, "url"),
                "body": raw_body,
            }
        else:
            raw_body = "\n\n".join(unescape(str(c)) for c in row[1:])
            item = {"title": unescape(str(row[0])), "date_raw": "",
                    "category": "", "tags": [], "url": "", "body": raw_body}
        # 表格导出的「正文」列可能是 HTML 片段，也可能是纯文本 + 实体（新浪官方导出）
        if re.search(r"<(?:p|div|img|br|span|a|strong|em|h[1-6]|blockquote)\b",
                     item["body"], re.I):
            item["body"] = html_to_markdown(item["body"])
        else:
            item["body"] = clean_plain_body(item["body"])
        # 官方导出通常没有分类/标签列，给默认值方便归档筛选
        if not item["category"]:
            item["category"] = FALLBACK_CATEGORY
        if not item["tags"]:
            item["tags"] = list(FALLBACK_TAGS)
        if item["title"] or item["body"]:
            item["file"] = src
            items.append(item)
    return items


def parse_html(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    # 已经是 Hexo 生成的文章页？只取 article-entry
    title = ""
    for pat in (r'<meta\s+property="og:title"\s+content="([^"]*)"',
                r'<h[12][^>]*class="[^"]*articalTitle[^"]*"[^>]*>(.*?)</h[12]>',
                r'<h[12][^>]*class="[^"]*titName[^"]*"[^>]*>(.*?)</h[12]>',
                r"<title>(.*?)</title>", r"<h1[^>]*>(.*?)</h1>"):
        m = re.search(pat, text, re.I | re.S)
        if m:
            title = strip_tags(m.group(1))
            title = re.sub(r"\s*[-|_]\s*(新浪博客|博客|blog).*$", "", title, flags=re.I).strip()
            if title:
                break
    date_raw = ""
    for pat in (r'<meta\s+property="article:published_time"\s+content="([^"]*)"',
                r'<span[^>]*class="[^"]*time[^"]*"[^>]*>(.*?)</span>',
                r'<div[^>]*class="[^"]*articalInfo[^"]*"[^>]*>(.*?)</div>'):
        m = re.search(pat, text, re.I | re.S)
        if m and DATE_RE.search(strip_tags(m.group(1))):
            date_raw = strip_tags(m.group(1))
            break
    if not date_raw:
        m = DATE_RE.search(strip_tags(text[:20000]))
        date_raw = m.group(0) if m else ""

    body_html = ""
    for marker in (r'<div[^>]*id="articlebody"', r'<div[^>]*class="[^"]*articalContent',
                   r'<div[^>]*class="[^"]*article-content', r'<div[^>]*class="[^"]*article-entry',
                   r'<div[^>]*class="[^"]*entry-content', r"<article\b"):
        body_html = inner_html_of_div(text, marker)
        if body_html and len(strip_tags(body_html)) > 20:
            break
    if not body_html:
        m = re.search(r"<body[^>]*>(.*?)</body>", text, re.I | re.S)
        body_html = m.group(1) if m else text
    body = html_to_markdown(body_html)
    if not title:
        title = path.stem
    # 若正文首行就是标题，去掉重复
    first = body.splitlines()[0].strip() if body.strip() else ""
    if first and (first == title or (len(first) < 60 and first in title)):
        body = "\n".join(body.splitlines()[1:]).lstrip()
    cat = ""
    m = re.search(r'class="[^"]*blog_class[^"]*"[^>]*>(.*?)</', text, re.I | re.S)
    if m:
        cat = strip_tags(m.group(1))
    url = ""
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', text, re.I)
    if m:
        url = m.group(1)
    return [{"title": title, "date_raw": date_raw, "category": cat, "tags": [],
             "url": url, "body": body, "file": str(path)}]


def parse_md(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = {}
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                kv = re.match(r"^(\w+)\s*:\s*(.*)$", line.strip())
                if kv:
                    fm[kv.group(1)] = kv.group(2).strip().strip("'\"")
            text = text[m.end():]
    title = fm.get("title") or path.stem
    d, _ = normalize_date(fm.get("date"), None) if fm.get("date") else (None, None)
    tags = [t.strip().strip("'\"") for t in fm.get("tags", "").strip("[]").split(",") if t.strip()]
    return [{"title": title, "date_raw": d or "", "category": fm.get("categories", ""),
             "tags": tags, "url": fm.get("source_url", ""), "body": text.strip(),
             "file": str(path)}]


def parse_txt(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    title = lines[0].strip() if lines else path.stem
    body = "\n".join(lines[1:]).strip()
    m = DATE_RE.search(path.name) or DATE_RE.search(text[:500])
    return [{"title": title[:120], "date_raw": m.group(0) if m else "",
             "category": "", "tags": [], "url": "", "body": body or text.strip(),
             "file": str(path)}]


def parse_xml(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    items = []
    for m in re.finditer(r"<(?:item|article|post|entry)\b[^>]*>(.*?)</(?:item|article|post|entry)>",
                         text, re.I | re.S):
        block = m.group(1)
        def field(*names):
            for n in names:
                mm = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (n, n), block, re.I | re.S)
                if mm:
                    return re.sub(r"<!\[CDATA\[|\]\]>", "", mm.group(1)).strip()
            return ""
        body_raw = field("content", "content:encoded", "description", "body", "正文", "内容")
        body = html_to_markdown(body_raw) if re.search(r"<[a-z]", body_raw, re.I) else body_raw
        items.append({"title": strip_tags(field("title", "标题")) or "未命名",
                      "date_raw": strip_tags(field("pubDate", "date", "时间", "发表时间")),
                      "category": strip_tags(field("category", "分类")),
                      "tags": [], "url": strip_tags(field("link", "url", "原文链接")),
                      "body": body, "file": str(path)})
    return items


def parse_json(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    data = []
    if path.suffix == ".ndjson" or (text.lstrip().startswith("{") and "\n{" in text):
        for line in text.splitlines():
            line = line.strip().rstrip(",")
            if line.startswith("{"):
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if not data:
        try:
            obj = json.loads(text)
            data = obj if isinstance(obj, list) else ([obj] if isinstance(obj, dict) else [])
        except json.JSONDecodeError:
            return []
    items = []
    for o in data:
        if not isinstance(o, dict):
            continue
        g = lambda *ks: next((str(o[k]) for k in ks if o.get(k) not in (None, "")), "")
        body = g("content", "body", "text", "markdown", "正文", "内容")
        if re.search(r"<[a-z]", body, re.I):
            body = html_to_markdown(body)
        tags = o.get("tags") or o.get("标签") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in re.split(r"[,，;；|/]", tags) if t.strip()]
        items.append({"title": g("title", "标题", "name") or "未命名",
                      "date_raw": g("date", "publishTime", "published_at", "时间", "发表时间"),
                      "category": g("category", "categories", "分类"),
                      "tags": tags, "url": g("url", "link", "原文链接", "source_url"),
                      "body": body, "file": str(path)})
    return items


PARSERS = {".xlsx": parse_xlsx, ".xls": parse_table_file, ".tsv": parse_delimited,
           ".csv": parse_csv, ".html": parse_html, ".htm": parse_html,
           ".md": parse_md, ".markdown": parse_md, ".txt": parse_txt,
           ".xml": parse_xml, ".json": parse_json, ".ndjson": parse_json}


# --------------------------------------------------------------------------
# 图片本地化
# --------------------------------------------------------------------------
def download_images(md, log):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    def repl(m):
        url = m.group(1)
        if not url.startswith("http") or url.startswith("https://www.westbar.cn"):
            return m.group(0)
        ext = re.search(r"\.(jpg|jpeg|png|gif|webp|bmp)(?:\?|$)", url, re.I)
        ext = "." + ext.group(1).lower() if ext else ".jpg"
        name = hashlib.md5(url.encode()).hexdigest()[:16] + ext
        dest = IMG_DIR / name
        if not dest.exists():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    dest.write_bytes(r.read())
                log.append(("OK", url, "/images/sina/" + name))
            except Exception as e:
                log.append(("FAIL", url, str(e)[:80]))
                return m.group(0)
        return m.group(0).replace(url, "/images/sina/" + name)
    return IMG_URL_RE.sub(repl, md)


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DEFAULT_INPUT), help="导出文件所在目录")
    ap.add_argument("--dry-run", action="store_true", help="只生成预览报告，不写文章")
    ap.add_argument("--download-images", action="store_true", help="下载外链图片到本地")
    ap.add_argument("--keep-duplicates", action="store_true", help="不跳过疑似重复文章")
    args = ap.parse_args()

    input_dir = Path(args.dir)
    if not input_dir.is_dir():
        raise SystemExit("找不到导入目录：%s\n请先创建并把新浪导出的文件放进去。" % input_dir)
    POSTS.mkdir(parents=True, exist_ok=True)

    files = [p for p in sorted(input_dir.rglob("*"))
             if p.is_file() and p.suffix.lower() in SUPPORTED
             and p.name not in ("import-report.md", "README.md")]
    if not files:
        raise SystemExit("导入目录里没有可识别的文件。支持：%s" % ", ".join(sorted(SUPPORTED)))

    items, errors = [], []
    for p in files:
        try:
            got = PARSERS[p.suffix.lower()](p)
            items.extend(got)
            print("  解析 %-45s -> %d 篇" % (p.name, len(got)))
        except Exception as e:
            errors.append((p.name, str(e)))

    existing = {}
    for p in POSTS.glob("*.md"):
        t = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^title:\s*(.+)$", t, re.M)
        if m:
            existing[m.group(1).strip().strip("'\"")] = p.name

    results, imglog = [], []
    for it in items:
        title = (it["title"] or "未命名").strip()
        body = (it["body"] or "").strip()
        if not body:
            errors.append((it["file"], "正文为空，跳过：%s" % title))
            continue
        day, full = normalize_date(it.get("date_raw"), None)
        if not it.get("date_raw"):
            m = DATE_RE.search(Path(it["file"]).name) or DATE_RE.search(body[:300])
            if m:
                day, full = normalize_date(m.group(0), None)
        dupe = title in existing
        if dupe and not args.keep_duplicates:
            results.append((title, day, "", "跳过（已存在同名文章：%s）" % existing[title], 0))
            continue
        md = yaml_front(title, full, it.get("category", ""), it.get("tags", []),
                        it.get("url", ""))
        md += body + "\n"
        if args.download_images:
            md = download_images(md, imglog)
        out = POSTS / ("%s-%s.md" % (day, safe_filename(title)))
        n = 1
        while out.exists():
            out = POSTS / ("%s-%s-%d.md" % (day, safe_filename(title), n))
            n += 1
        if not args.dry_run:
            out.write_text(md, encoding="utf-8")
        results.append((title, day, out.name, "预览" if args.dry_run else "已导入",
                        len(IMG_URL_RE.findall(md))))

    lines = ["# 新浪博客导入报告", "",
             "生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "输入目录：`%s`" % input_dir,
             "识别文件 %d 个，解析出 %d 篇，实际写入 %d 篇%s" %
             (len(files), len(items),
              sum(1 for r in results if r[3] in ("已导入", "预览")),
              "（预览模式，未写文件）" if args.dry_run else ""), "",
             "## 逐篇明细", "", "| 标题 | 原文日期 | 生成文件 | 状态 | 图片 |",
             "| --- | --- | --- | --- | --- |"]
    for t, d, fn, st, n in results:
        lines.append("| %s | %s | `%s` | %s | %d |" %
                     (t.replace("|", "\\|"), d, fn, st, n))
    if imglog:
        ok = sum(1 for x in imglog if x[0] == "OK")
        lines += ["", "## 图片下载", "", "成功 %d，失败 %d" % (ok, len(imglog) - ok), ""]
        for st, url, note in imglog:
            lines.append("- [%s] `%s` → %s" % (st, url, note))
        lines += ["", "> 下载失败的链接仍保留在正文里，需手动补图（放到 `source/images/`）。"]
    if errors:
        lines += ["", "## 需要人工处理", ""] + ["- `%s`：%s" % e for e in errors]
    lines += ["", "## 导入后请做三件事", "",
              "1. `npm run build` 本地生成，打开 `public/` 检查排版和图片；",
              "2. 逐篇核对**日期**——新浪官方 Excel 导出常丢时间，识别不到时默认用今天；",
              "3. 确认无误后 `npm run deploy` 发布。", ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n共 %d 篇待处理，写入 %d 篇。报告：%s" %
          (len(items), sum(1 for r in results if r[3] in ("已导入", "预览")), REPORT))


if __name__ == "__main__":
    main()
