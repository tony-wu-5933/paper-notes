# Paper Notes 論文筆記庫

用 AI agent 整理論文筆記的靜態網站。所有規則寫在 [`AGENTS.md`](./AGENTS.md)，
AI 讀完後就能用同一套格式持續新增筆記：結構固定、搭配原文圖片解說、實驗數字都標出處、自己的推論另外標記。

- 網站：`https://<你的帳號>.github.io/paper-notes/`
- 規則：[`AGENTS.md`](./AGENTS.md)（[`CLAUDE.md`](./CLAUDE.md) 指向它）

## 新增一篇筆記

1. 把 PDF 放進 `inbox/`，或準備 arXiv 連結
2. 對 Claude Code / Codex 說：

   ```
   依照 AGENTS.md 整理 inbox/xxx.pdf，我想看它的評估方法
   ```

3. AI 會在 `notes/` 建立筆記，並執行檢查與建置
4. `git add . && git commit -m "add note" && git push`

## 手動建置

```bash
pip install markdown pyyaml pymupdf   # pymupdf 用於擷取 PDF 圖片
python3 scripts/check.py   # 規則檢查
python3 scripts/build.py   # 產生 docs/
```

## 結構

| 路徑 | 用途 |
|---|---|
| `notes/` | 論文筆記（每篇一個 Markdown） |
| `templates/paper-note.md` | 筆記模板 |
| `data/tags.yml` | 允許的標籤（中文名稱與分組） |
| `assets/figures/` | 每篇筆記的圖片 |
| `layout/` | 網頁外觀（白底黑字單欄） |
| `scripts/` | 檢查與建置腳本 |
| `docs/` | 建置輸出，GitHub Pages 從這裡發布 |
| `inbox/` | 放 PDF 的地方（不會上傳） |

## 發布設定

GitHub repo → Settings → Pages → Source 選 **Deploy from a branch**，
Branch 選 `main`、資料夾選 `/docs`。
