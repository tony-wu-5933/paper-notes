#!/usr/bin/env python3
"""檢查 notes/ 中的筆記是否符合 AGENTS.md 的規則。

用法：python3 scripts/check.py
有任何 ERROR 時以 exit code 1 結束。不要為了通過檢查而修改本檔，請修正筆記。
"""
import datetime as dt
import re
import sys

from common import (NOTES_DIR, OPTIONAL_SECTION, SECTIONS, SUBSECTIONS,
                    load_tags, note_paths, read_markdown, split_sections)

FILENAME_RE = re.compile(r"^\d{4}-[a-z0-9]+(-[a-z0-9]+)*\.md$")
REQUIRED = ["title", "short_title", "authors", "year", "venue", "source_url",
            "tags", "status", "input", "date_read"]
STATUS = {"精讀", "略讀"}
INPUT = {"arxiv", "pdf", "url"}
# 出處：（Table 2）（Fig. 7）（§4.3）（Appendix C），可組合
SOURCE_RE = re.compile(r"（[^（）]*(Table|Fig\.|§|Appendix)[^（）]*）\s*[。.]?\s*$")
NUMBER_RE = re.compile(r"\d")
BANNED = ["完美解決", "完全解決", "大幅超越所有"]


def check_note(path, tags):
    errors, warns = [], []
    name = path.name
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
    note_tags = meta.get("tags") or []
    if not isinstance(note_tags, list):
        errors.append("tags 必須是清單")
        note_tags = []
    if not 2 <= len(note_tags) <= 6:
        errors.append("tags 數量需為 2～6 個")
    for t in note_tags:
        if t not in tags:
            errors.append(f"標籤「{t}」不在 data/tags.yml，請先新增到清單")

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

    summary = content.get("一句話摘要", "").strip()
    if summary and len([s for s in re.split(r"[。！？]", summary) if s.strip()]) > 2:
        warns.append("一句話摘要似乎超過一句")

    # 實驗章節：所有含數字的條列都要有出處
    for line in content.get("3. 實驗", "").splitlines():
        s = line.strip()
        if s.startswith("- ") and NUMBER_RE.search(s) and not SOURCE_RE.search(s):
            errors.append(f"實驗數字缺少出處（Table / Fig. / § / Appendix）：{s[:60]}…")

    # 我的觀察：每點都要 [補充]
    obs = content.get("5. 限制", "").split("### 我的觀察")[-1]
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

    # 引用長度
    for line in body.splitlines():
        if line.startswith(">") and len(line) > 200:
            errors.append("引用原文超過 200 字元，請改寫")

    for w in BANNED:
        if w in body:
            errors.append(f"出現誇大用語「{w}」")

    if "```bibtex" not in content.get("8. BibTeX", ""):
        errors.append("8. BibTeX 需包含 ```bibtex 程式碼區塊")

    terms = [l for l in content.get("7. 關鍵名詞", "").splitlines()
             if l.startswith("|") and not set(l) <= set("|- :")]
    if terms and not 5 <= len(terms) - 1 <= 12:
        warns.append("關鍵名詞建議 5～12 個")

    return errors, warns


def main():
    tags = load_tags()
    paths = note_paths()
    if not paths:
        print("notes/ 中沒有任何筆記")
    total_err = 0
    for p in paths:
        errors, warns = check_note(p, tags)
        status = "OK  " if not errors else "FAIL"
        print(f"[{status}] {p.relative_to(NOTES_DIR.parent)}")
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
