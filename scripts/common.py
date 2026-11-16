"""build.py 與 check.py 共用的設定與工具函式。"""
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
PAGES_DIR = ROOT / "pages"
LAYOUT_DIR = ROOT / "layout"
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"
FIG_DIR = ASSETS_DIR / "figures"
OUT_DIR = ROOT / "docs"

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.S)
# ![圖說](路徑 "出處")
IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(\s*([^\s)]+)(?:\s+"([^"]*)")?\s*\)')

# 章節標題（順序固定，見 AGENTS.md 6.1）。第 6 節只有在 front matter 有 purpose 時才出現。
SECTIONS = [
    "一句話摘要",
    "1. 問題與動機",
    "2. 貢獻",
    "3. 方法",
    "4. 實驗",
    "5. 限制",
    "6. 與我研究的關聯",
    "7. 關鍵名詞",
    "8. BibTeX",
]
OPTIONAL_SECTION = "6. 與我研究的關聯"
METHOD_SECTION = "3. 方法"
EXPERIMENT_SECTION = "4. 實驗"
LIMIT_SECTION = "5. 限制"
SUBSECTIONS = {
    EXPERIMENT_SECTION: ["設定", "結果"],
    LIMIT_SECTION: ["作者自述", "我的觀察"],
}
REQUIRED_TAG_GROUPS = ["研究領域", "技術方法"]
FIG_EXPLAIN = "**怎麼看這張圖：**"


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
    """回傳 (groups: list[str], tags: dict[key -> {label, group}])。"""
    data = yaml.safe_load((DATA_DIR / "tags.yml").read_text(encoding="utf-8")) or {}
    return data.get("groups", []), data.get("tags", {})


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


def is_open_license(meta) -> bool:
    return str(meta.get("license", "")).strip().upper().startswith("CC")


def note_paths():
    return sorted(p for p in NOTES_DIR.glob("*.md"))
