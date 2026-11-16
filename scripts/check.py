#!/usr/bin/env python3
"""檢查 notes/ 中的筆記是否符合 AGENTS.md 的規則。

用法：python3 scripts/check.py
有任何 ERROR 時以 exit code 1 結束。不要為了通過檢查而修改本檔，請修正筆記。
"""
import datetime as dt
import re
import sys

from common import (EXPERIMENT_SECTION, FIG_DIR, FIG_EXPLAIN, IMAGE_RE,
                    LIMIT_SECTION, METHOD_SECTION, NOTES_DIR, OPTIONAL_SECTION,
                    REQUIRED_TAG_GROUPS, SECTIONS, SUBSECTIONS, is_open_license,
                    load_tags, note_paths, read_markdown, split_sections)

FILENAME_RE = re.compile(r"^\d{4}-[a-z0-9]+(-[a-z0-9]+)*\.md$")
IMG_NAME_RE = re.compile(r"^(fig\d+[a-z]?|table\d+|diagram-[a-z0-9-]+)\.(png|jpg|svg)$")
REQUIRED = ["title", "short_title", "authors", "year", "venue", "source_url",
            "tags", "status", "input", "date_read"]
STATUS = {"精讀", "略讀"}
INPUT = {"arxiv", "pdf", "url"}
# 出處：（Table 2）（Fig. 7）（§4.3）（Appendix C），可組合
SOURCE_RE = re.compile(r"（[^（）]*(Table|Fig\.|§|Appendix)[^（）]*）")
# 「獨立的數字」：排除 GPT-4、o1-mini、CVE-2017-7494 這類名稱中的數字
NUMBER_RE = re.compile(r"(?<![\w.\-/])\d+(?:\.\d+)?(?![\w\-/])")
BANNED = ["完美解決", "完全解決", "大幅超越所有"]


def check_figures(slug, meta, body, content, errors, warns):
    lines = body.splitlines()
    used = set()
    open_lic = is_open_license(meta)
    for i, line in enumerate(lines):
        for alt, src, title in IMAGE_RE.findall(line):
            name = src.rsplit("/", 1)[-1]
            used.add(name)
            prefix = f"../assets/figures/{slug}/"
            if not src.startswith(prefix):
                errors.append(f"圖片路徑需為 {prefix}<檔名>：{src}")
                continue
            if not IMG_NAME_RE.match(name):
                errors.append(f"圖片檔名需為 figN / tableN / diagram-xxx：{name}")
            if not (FIG_DIR / slug / name).exists():
                errors.append(f"找不到圖片檔案：assets/figures/{slug}/{name}")
            if not alt.strip():
                errors.append(f"圖片缺少中文圖說：{name}")
            if not title.strip():
                errors.append(f'圖片缺少出處（引號內，例："原文 Fig. 1，CC BY 4.0"）：{name}')
            is_original = name.startswith(("fig", "table"))
            if is_original and not open_lic:
                errors.append(f"論文沒有 CC 開放授權，不能放原文圖片：{name}（改用文字或 diagram-*）")
            if is_original and title and "原文" not in title:
                errors.append(f"原文圖片的出處需寫「原文 Fig. N，授權」：{name}")
            nxt = next((l.strip() for l in lines[i + 1:] if l.strip()), "")
            if not nxt.startswith(FIG_EXPLAIN):
                errors.append(f"圖片下一段需以「{FIG_EXPLAIN}」開頭解說：{name}")
    if open_lic and not IMAGE_RE.search(content.get(METHOD_SECTION, "")):
        errors.append("論文有開放授權，「3. 方法」需放整體架構圖")
    folder = FIG_DIR / slug
    if folder.exists():
        for f in folder.iterdir():
            if f.name not in used:
                warns.append(f"圖片未被筆記使用：assets/figures/{slug}/{f.name}")


def check_note(path, groups, tags):
    errors, warns = [], []
    name, slug = path.name, path.stem
    if not FILENAME_RE.match(name):
        errors.append("檔名需為 <year>-<作者姓氏>-<簡稱>.md（小寫 kebab-case）")

    try:
        meta, body = read_markdown(path)
    except Exception as e:  # noqa: BLE001
        return [str(e)], warns

    # --- front matter ---
    for key in REQUIRED:
        if meta.get(key) in (None, "", []):
            errors.append(f"front matter 缺少必填欄位：{key}")
    year = meta.get("year")
    if year is not None and not (isinstance(year, int) and 1950 <= year <= 2100):
        errors.append("year 必須是四位數年份")
    elif year is not None and not name.startswith(f"{year}-"):
        errors.append(f"檔名開頭年份應與 year（{year}）一致")
    if meta.get("status") and meta["status"] not in STATUS:
        errors.append(f"status 只能是 {sorted(STATUS)}")
    if meta.get("input") and meta["input"] not in INPUT:
        errors.append(f"input 只能是 {sorted(INPUT)}")
    d = meta.get("date_read")
    if d is not None and not isinstance(d, dt.date):
        try:
            dt.date.fromisoformat(str(d))
        except ValueError:
            errors.append("date_read 格式需為 YYYY-MM-DD")
    if not isinstance(meta.get("authors", []), list):
        errors.append("authors 必須是清單")
    for key in ("source_url", "code_url"):
        v = meta.get(key)
        if v and not str(v).startswith("https://"):
            errors.append(f"{key} 必須是 https:// 開頭的網址")

    # --- 標籤 ---
    note_tags = meta.get("tags") or []
    if not isinstance(note_tags, list):
        errors.append("tags 必須是清單")
        note_tags = []
    if not 2 <= len(note_tags) <= 6:
        errors.append("tags 數量需為 2～6 個")
    for t in note_tags:
        if t not in tags:
            errors.append(f"標籤「{t}」不在 data/tags.yml，請先新增到清單")
    used_groups = {tags[t].get("group") for t in note_tags if t in tags}
    for g in REQUIRED_TAG_GROUPS:
        if g not in used_groups:
            errors.append(f"標籤需至少包含一個「{g}」分組的標籤")

    # --- 章節結構 ---
    sections = split_sections(body)
    titles = [t for t, _ in sections]
    expected = [s for s in SECTIONS if s != OPTIONAL_SECTION or meta.get("purpose")]
    if titles != expected:
        if OPTIONAL_SECTION in titles and not meta.get("purpose"):
            errors.append("有第 6 節「與我研究的關聯」但 front matter 沒有 purpose")
        elif meta.get("purpose") and OPTIONAL_SECTION not in titles:
            errors.append("front matter 有 purpose，但缺少第 6 節「與我研究的關聯」")
        else:
            errors.append("章節標題或順序不符，應為：" + " / ".join(expected))
    content = dict(sections)

    for sec, subs in SUBSECTIONS.items():
        found = re.findall(r"^### (.+)$", content.get(sec, ""), re.M)
        if [s.strip() for s in found] != subs:
            errors.append(f"「{sec}」的子標題應為 {' / '.join(subs)}")

    # 實驗章節：每一行含數字的內容都要有出處
    for line in content.get(EXPERIMENT_SECTION, "").splitlines():
        s = line.strip()
        if (not s or s.startswith("#") or s.startswith("![") or set(s) <= set("|-: ")):
            continue
        if NUMBER_RE.search(s) and not SOURCE_RE.search(s):
            errors.append(f"實驗數字缺少出處（Table / Fig. / § / Appendix）：{s[:60]}…")

    # 我的觀察：每點都要 [補充]
    obs = content.get(LIMIT_SECTION, "").split("### 我的觀察")[-1]
    for line in obs.splitlines():
        s = line.strip()
        if s.startswith("- ") and not s.startswith("- [補充]"):
            errors.append(f"「我的觀察」每點需以 [補充] 開頭：{s[:40]}…")

    # 巢狀條列需 4 格縮排
    in_code = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and re.match(r"^ {1,3}[-*] ", line):
            errors.append(f"巢狀條列需用 4 個空格縮排：{line.strip()[:40]}…")

    for line in body.splitlines():
        if line.startswith(">") and len(line) > 200:
            errors.append("引用原文超過 200 字元，請改寫")
    for w in BANNED:
        if w in body:
            errors.append(f"出現誇大用語「{w}」")

    check_figures(slug, meta, body, content, errors, warns)

    if "```bibtex" not in content.get("8. BibTeX", ""):
        errors.append("8. BibTeX 需包含 ```bibtex 程式碼區塊")
    terms = [l for l in content.get("7. 關鍵名詞", "").splitlines()
             if l.startswith("|") and not set(l) <= set("|- :")]
    if terms and len(terms) - 1 < 5:
        warns.append("關鍵名詞建議至少 5 個")
    return errors, warns


def main():
    groups, tags = load_tags()
    errors_cfg = [f"data/tags.yml：標籤 {k} 的 group「{v.get('group')}」不在 groups 中"
                  for k, v in tags.items() if v.get("group") not in groups]
    errors_cfg += [f"data/tags.yml：標籤 {k} 缺少 label" for k, v in tags.items() if not v.get("label")]
    for e in errors_cfg:
        print(f"   ERROR  {e}")

    paths = note_paths()
    total_err = len(errors_cfg)
    for p in paths:
        errors, warns = check_note(p, groups, tags)
        print(f"[{'OK  ' if not errors else 'FAIL'}] {p.relative_to(NOTES_DIR.parent)}")
        for e in errors:
            print(f"   ERROR  {e}")
        for w in warns:
            print(f"   WARN   {w}")
        total_err += len(errors)
    if total_err:
        print(f"\n{total_err} 個錯誤，請修正後再建置。")
        sys.exit(1)
    print(f"\nALL CHECKS PASSED（{len(paths)} 篇筆記）")


if __name__ == "__main__":
    main()
