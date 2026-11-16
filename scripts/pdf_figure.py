#!/usr/bin/env python3
"""從論文 PDF 擷取圖片，供筆記使用（規則見 AGENTS.md 第 7 節）。

需要套件：pip install pymupdf

用法：
  # 1. 列出 PDF 中所有 Figure / Table 的圖說位置（頁碼從 1 開始）
  python3 scripts/pdf_figure.py list inbox/paper.pdf

  # 2. 自動擷取某張圖（依圖說往上找圖形範圍）
  python3 scripts/pdf_figure.py auto inbox/paper.pdf "Figure 1" assets/figures/<slug>/fig1.png

  # 3. 自動結果不理想時，手動指定範圍（PDF 座標，單位 pt，左上為原點）
  python3 scripts/pdf_figure.py crop inbox/paper.pdf <page> <x0> <y0> <x1> <y1> <out.png>

  # 輔助：把整頁輸出成圖片，用來判斷手動範圍
  python3 scripts/pdf_figure.py page inbox/paper.pdf <page> <out.png>
"""
import re
import sys
from pathlib import Path

import pymupdf

ZOOM = 3  # 約 216 dpi，放大後仍清楚


def save_clip(page, rect, out):
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=rect)
    pix.save(out)
    print(f"saved {out}  ({pix.width}x{pix.height}px, page {page.number + 1}, "
          f"rect=({rect.x0:.0f},{rect.y0:.0f},{rect.x1:.0f},{rect.y1:.0f}))")


def find_caption(doc, label):
    pat = re.compile(rf"^{re.escape(label)}\s*[:.]")
    for page in doc:
        for b in page.get_text("blocks"):
            if pat.match(b[4].strip()):
                return page, pymupdf.Rect(b[:4])
    raise SystemExit(f"找不到圖說：{label}")


def auto(doc, label, out):
    """以圖說為基準：收集圖說上方、同一欄內的向量圖形與點陣圖，取聯集。"""
    page, cap = find_caption(doc, label)
    mid = page.rect.width / 2
    if cap.x1 <= mid + 10:
        col = (0, mid)
    elif cap.x0 >= mid - 10:
        col = (mid, page.rect.width)
    else:
        col = (0, page.rect.width)

    def in_col(r):
        return r.x0 >= col[0] - 5 and r.x1 <= col[1] + 5

    shapes = [d["rect"] for d in page.get_drawings()]
    shapes += [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
    shapes = [r for r in shapes if in_col(r) and r.y1 <= cap.y0 + 2 and r.width * r.height > 4]

    # 由下往上收集，遇到大於 25pt 的空白就停止（代表進入內文）
    shapes.sort(key=lambda r: -r.y1)
    region, top = None, cap.y0
    for r in shapes:
        if r.y1 < top - 25:
            break
        region = r if region is None else region | r
        top = min(top, r.y0)
    if region is None:
        raise SystemExit("自動擷取失敗，請改用 crop 手動指定範圍")

    # 納入圖形範圍內的文字標籤（座標軸、圖例等）
    for b in page.get_text("blocks"):
        br = pymupdf.Rect(b[:4])
        if in_col(br) and br.y1 <= cap.y0 and br.intersects(region):
            region |= br
    save_clip(page, region + (-4, -4, 4, 4), out)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, pdf = sys.argv[1], sys.argv[2]
    doc = pymupdf.open(pdf)
    if cmd == "list":
        for page in doc:
            for b in page.get_text("blocks"):
                t = b[4].strip().replace("\n", " ")
                if re.match(r"^(Figure|Fig\.|Table)\s*\d+\s*[:.]", t):
                    print(f"p.{page.number + 1:<3} {t[:80]}")
    elif cmd == "auto":
        auto(doc, sys.argv[3], sys.argv[4])
    elif cmd == "crop":
        page = doc[int(sys.argv[3]) - 1]
        x0, y0, x1, y1 = map(float, sys.argv[4:8])
        save_clip(page, pymupdf.Rect(x0, y0, x1, y1), sys.argv[8])
    elif cmd == "page":
        page = doc[int(sys.argv[3]) - 1]
        save_clip(page, page.rect, sys.argv[4])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
