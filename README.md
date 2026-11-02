# Third-party Package Report Skill

盤點 .NET API 與 Angular 的第三方套件，以使用證據與實際版本授權產出 Markdown 清單，交付前由獨立唯讀子代理檢核。

## 安裝至 Claude Code

需要 Git、Python 3，以及支援子代理的 Claude Code。將此專案安裝至個人 skills 目錄：

```sh
git clone https://github.com/zokmi/third-party-package-report-skill.git ~/.claude/skills/generating-third-party-package-report
```

若目標目錄已存在，先備份既有版本。重新啟動 Claude Code 後，請它使用 `generating-third-party-package-report` 盤點指定 API 或前端入口。

## 使用

提供 `.csproj`、`.sln` 或 `package.json` 入口；Angular 請先安裝專案相依套件。

```sh
python -I scripts/collect_packages.py path/to/App.Api.csproj path/to/frontend/package.json > packages.json
```

腳本只輸出 JSON 證據；Markdown 報告由代理依 `SKILL.md` 與 `assets/report-template.md` 產生，預設路徑為 `docs/<範圍>-第三方套件清單.md`。

- 只列使用中的套件，固定七欄，附授權彙總。
- 收集直接參考、版本、授權中繼資料及使用證據；不展開所有遞移相依。
- .NET 會沿 ProjectReference 展開；授權讀本機 NuGet 快取或 node_modules，缺漏由代理另行查證。
- `not-found` 不等於可移除，須人工排查。
- 最終報告須由唯讀子代理讀取報告及原始證據，全部適用項目 PASS 才交付；修改後重新檢核。
- 無法啟動子代理或證據不足時保留草稿並回報缺口。

## 檔案

| 檔案 | 用途 |
| --- | --- |
| SKILL.md | 分析、Markdown 產出與子代理檢核流程 |
| assets/report-template.md | 七欄報告及授權彙總樣板 |
| scripts/collect_packages.py | 使用 Python 標準函式庫收集 .NET／Angular 套件證據 |

此工具協助整理授權證據，不取代個別套件授權條款的查證。