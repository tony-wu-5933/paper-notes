#!/usr/bin/env python3
"""把 notes/ 與 pages/ 轉成靜態網站，輸出到 docs/（GitHub Pages 發布來源）。

用法：python3 scripts/build.py
需要套件：pip install markdown pyyaml
"""
import html
import json
import re
import shutil

import markdown
from markdown.extensions.toc import slugify_unicode

from common import (ASSETS_DIR, LAYOUT_DIR, OUT_DIR, PAGES_DIR, load_tags,
                    note_paths, read_markdown, split_sections)

# 部署在 GitHub Pages 時，頁面上的 JavaScript 會把這個字串換成真正的 <user>/<repo>
REPO_PLACEHOLDER = "OWNER/REPO"
BASE = (LAYOUT_DIR / "base.html").read_text(encoding="utf-8")

FIGURE_RE = re.compile(r'<p>\s*<img alt="([^"]*)" src="([^"]+)"(?: title="([^"]*)")?\s*/?>\s*</p>')


def md_convert(text: str):
    """回傳 (html, toc_tokens)。"""
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"slugify": slugify_unicode,
                                                      "toc_depth": "2-3"}})
    out = md.convert(text)
    # 圖片 → <figure>，點擊開啟原尺寸
    out = FIGURE_RE.sub(
        lambda m: (f'<figure><a href="{m.group(2)}" target="_blank" rel="noopener">'
                   f'<img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy"></a>'
                   f'<figcaption>{m.group(1)}'
                   f'{"<span class=src>" + m.group(3) + "</span>" if m.group(3) else ""}'
                   f'</figcaption></figure>'), out)
    # [補充] 轉成小標記，讓讀者一眼區分整理者的推論
    out = out.replace("[補充]", '<span class="supplement">補充</span>')
    return out, md.toc_tokens


def toc_html(tokens):
    items = []
    for t in tokens:
        sub = "".join(f'<li><a href="#{c["id"]}">{c["name"]}</a></li>' for c in t["children"])
        items.append(f'<li><a href="#{t["id"]}">{t["name"]}</a>'
                     f'{"<ul>" + sub + "</ul>" if sub else ""}</li>')
    return f'<nav class="toc"><div class="toc-title">目錄</div><ol>{"".join(items)}</ol></nav>'


def render(page_title, content, root, description="", footer="", scripts=""):
    out = BASE
    for k, v in {
        "page_title": page_title, "description": description, "root": root,
        "content": content, "footer": footer, "scripts": scripts,
    }.items():
        out = out.replace("{{" + k + "}}", v)
    return out.replace("{{repo}}", REPO_PLACEHOLDER)


def esc(s) -> str:
    return html.escape(str(s))


def tag_label(tags, t):
    return tags.get(t, {}).get("label", t)


def build_note(path, tags):
    meta, body = read_markdown(path)
    slug = path.stem
    sections = dict(split_sections(body))
    summary = sections.get("一句話摘要", "").strip()
    body_html, tokens = md_convert(body)

    authors = meta.get("authors", [])
    links = [f'<a href="{esc(meta["source_url"])}">原文</a>']
    if meta.get("code_url"):
        links.append(f'<a href="{esc(meta["code_url"])}">程式碼</a>')
    tag_html = "".join(
        f'<a class="tag" href="../index.html#tag={esc(t)}">{esc(tag_label(tags, t))}</a>'
        for t in meta.get("tags", []))
    purpose = f'<p class="meta">閱讀目的：{esc(meta["purpose"])}</p>' if meta.get("purpose") else ""
    head = f"""<div class="note-head">
<h1>{esc(meta['title'])}</h1>
<p class="meta">{esc(', '.join(authors))}</p>
<p class="meta">{esc(meta['venue'])} · {esc(meta['year'])}{' · ' + esc(meta['license']) if meta.get('license') else ''} · {' · '.join(links)}</p>
<p class="meta">{esc(meta['status'])} · 整理於 {esc(meta['date_read'])}</p>
{purpose}
<div class="tags">{tag_html}</div>
</div>"""
    footer = (f'本筆記依 <a href="https://github.com/{{{{repo}}}}/blob/main/AGENTS.md">AGENTS.md</a> 規則由 AI 整理'
              f' · 輸入：{esc(meta["input"])}'
              f' · <a href="https://github.com/{{{{repo}}}}/blob/main/notes/{slug}.md">原始 Markdown</a>')
    page = render(f"{meta['short_title']} — Paper Notes", head + toc_html(tokens) + body_html, "../",
                  description=esc(re.sub(r"\s+", " ", summary)[:150]), footer=footer)
    (OUT_DIR / "notes" / f"{slug}.html").write_text(page, encoding="utf-8")
    return {
        "slug": slug, "short": meta["short_title"], "title": meta["title"],
        "year": meta["year"], "venue": meta["venue"], "tags": meta.get("tags", []),
        "status": meta["status"], "summary": summary, "date_read": str(meta["date_read"]),
        "authors": authors,
    }


def build_index(entries, groups, tags):
    entries.sort(key=lambda e: (int(e["year"]), e["date_read"]), reverse=True)  # 新到舊
    counts = {}
    for e in entries:
        for t in e["tags"]:
            counts[t] = counts.get(t, 0) + 1

    items = []
    for e in entries:
        labels = [tag_label(tags, t) for t in e["tags"]]
        search = " ".join([e["short"], e["title"], e["venue"], " ".join(e["authors"]),
                           e["summary"], " ".join(e["tags"]), " ".join(labels)]).lower()
        first = (e["authors"][0] + (" et al." if len(e["authors"]) > 1 else "")) if e["authors"] else ""
        items.append(f"""<li data-tags="{esc(' '.join(e['tags']))}" data-search="{esc(search)}">
<a class="pt" href="notes/{e['slug']}.html">{esc(e['short'])}</a>
<div class="full">{esc(e['title'])}</div>
<div class="meta">{esc(first)} · {esc(e['venue'])} · {esc(e['status'])}</div>
<p class="one">{esc(e['summary'])}</p>
<div>{''.join(f'<span class="tag">{esc(l)}</span>' for l in labels)}</div>
</li>""")

    # 分組標籤按鈕：只顯示有筆記使用的標籤，附篇數
    rows = []
    for g in groups:
        ts = [t for t, v in tags.items() if v.get("group") == g and t in counts]
        if not ts:
            continue
        ts.sort(key=lambda t: (-counts[t], tag_label(tags, t)))
        btns = "".join(f'<button class="filter" data-tag="{esc(t)}">{esc(tag_label(tags, t))}'
                       f'<span class="count">{counts[t]}</span></button>' for t in ts)
        rows.append(f'<div class="filter-row"><span class="group">{esc(g)}</span><div>{btns}</div></div>')

    content = f"""<h1>論文筆記</h1>
<p class="intro">由 AI agent 依照 <a href="https://github.com/{{{{repo}}}}/blob/main/AGENTS.md">AGENTS.md</a> 規則整理的論文筆記。每篇搭配原文圖片解說，實驗數字皆標註原文出處。共 {len(entries)} 篇。</p>
<div class="controls">
<input id="q" type="search" placeholder="搜尋標題、作者、摘要、標籤…" aria-label="搜尋">
<div class="filters">
<div class="filter-row"><span class="group">篩選</span><div><button class="filter on" data-tag="">全部<span class="count">{len(entries)}</span></button></div></div>
{''.join(rows)}
</div>
</div>
<ul class="paper-list" id="list">
{''.join(items)}
</ul>
<p class="empty" id="empty">沒有符合條件的筆記。</p>"""
    script = """<script>
(function () {
  var q = document.getElementById('q'), items = document.querySelectorAll('#list li'),
      btns = document.querySelectorAll('.filter'), empty = document.getElementById('empty'), tag = '';
  function apply() {
    var kw = q.value.trim().toLowerCase(), n = 0;
    items.forEach(function (li) {
      var ok = (!tag || li.dataset.tags.split(' ').indexOf(tag) >= 0) &&
               (!kw || li.dataset.search.indexOf(kw) >= 0);
      li.style.display = ok ? '' : 'none'; if (ok) n++;
    });
    empty.style.display = n ? 'none' : 'block';
    btns.forEach(function (b) { b.classList.toggle('on', b.dataset.tag === tag); });
  }
  btns.forEach(function (b) { b.addEventListener('click', function () {
    tag = (tag === b.dataset.tag) ? '' : b.dataset.tag;
    history.replaceState(null, '', tag ? '#tag=' + tag : location.pathname); apply();
  }); });
  q.addEventListener('input', apply);
  var m = location.hash.match(/^#tag=(.+)$/); if (m) tag = decodeURIComponent(m[1]);
  apply();
})();
</script>"""
    footer = 'Paper Notes · <a href="about.html">這個網站如何產生</a>'
    page = render("Paper Notes — 論文筆記", content, "", description="AI agent 依規則整理的論文筆記",
                  footer=footer, scripts=script)
    (OUT_DIR / "index.html").write_text(page, encoding="utf-8")
    (OUT_DIR / "notes.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2),
                                        encoding="utf-8")


def build_pages():
    for p in sorted(PAGES_DIR.glob("*.md")):
        meta, body = read_markdown(p)
        body_html, _ = md_convert(body)
        content = f"<h1>{esc(meta['title'])}</h1>\n" + body_html
        page = render(f"{meta['title']} — Paper Notes", content, "",
                      footer='Paper Notes · <a href="index.html">回論文列表</a>')
        (OUT_DIR / f"{p.stem}.html").write_text(page, encoding="utf-8")


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "notes").mkdir(parents=True)
    groups, tags = load_tags()
    entries = [build_note(p, tags) for p in note_paths()]
    build_index(entries, groups, tags)
    build_pages()
    shutil.copy(LAYOUT_DIR / "style.css", OUT_DIR / "style.css")
    if ASSETS_DIR.exists():
        shutil.copytree(ASSETS_DIR, OUT_DIR / "assets")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")  # 不讓 GitHub Pages 再跑 Jekyll
    print(f"Built {len(entries)} note(s) → docs/")


if __name__ == "__main__":
    main()
