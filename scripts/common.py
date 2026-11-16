"""build.py 與 check.py 共用的工具函式。"""
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
PAGES_DIR = ROOT / "pages"
LAYOUT_DIR = ROOT / "layout"
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "docs"

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.S)

# 章節標題（順序固定）。第 6 節只有在 front matter 有 purpose 時才出現。
SECTIONS = [
    "一句話摘要",
    "1. 問題與動機",
    "2. 方法",
    "3. 實驗",
    "4. 貢獻",
    "5. 限制",
    "6. 與我研究的關聯",
    "7. 關鍵名詞",
    "8. BibTeX",
]
OPTIONAL_SECTION = "6. 與我研究的關聯"
SUBSECTIONS = {
    "3. 實驗": ["設定", "結果"],
    "5. 限制": ["作者自述", "我的觀察"],
}


def read_markdown(path: Path):
    """回傳 (front_matter: dict, body: str)。沒有 front matter 時丟出 ValueError。"""
    text = path.read_text(encoding="utf-8")
    m = FRONT_MATTER_RE.match(text)
    if not m:
        raise ValueError("缺少 YAML front matter（檔案開頭需為 --- ... ---）")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("front matter 格式錯誤")
    return meta, m.group(2)


def load_tags():
    return yaml.safe_load((DATA_DIR / "tags.yml").read_text(encoding="utf-8")) or {}


def split_sections(body: str):
    """依 `## ` 切出章節，回傳 [(標題, 內文)]，忽略程式碼區塊中的 ##。"""
    sections, title, buf, in_code = [], None, [], False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith("## "):
            if title is not None:
                sections.append((title, "\n".join(buf)))
            title, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if title is not None:
        sections.append((title, "\n".join(buf)))
    return sections


def note_paths():
    return sorted(p for p in NOTES_DIR.glob("*.md"))
