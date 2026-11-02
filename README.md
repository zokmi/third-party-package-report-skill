# Third-party Package Report Skill

盤點 .NET API 與 Angular 的第三方套件，以使用證據與實際版本授權產出 Markdown 清單，交付前由獨立唯讀子代理檢核。

## 安裝

需要 Git、Python 3，以及可啟動獨立子代理的 Claude Code 或 Codex。以下為個人 skill 安裝，兩個工具可分別安裝；若目標目錄已存在，先備份既有版本。

### Claude Code

Bash／zsh：

```sh
mkdir -p ~/.claude/skills
git clone https://github.com/zokmi/third-party-package-report-skill.git ~/.claude/skills/generating-third-party-package-report
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$HOME/.claude/skills" | Out-Null
git clone https://github.com/zokmi/third-party-package-report-skill.git "$HOME/.claude/skills/generating-third-party-package-report"
```

重新啟動 Claude Code，請它「使用 generating-third-party-package-report 盤點指定 API 或前端入口」。

### Codex

Bash／zsh：

```sh
mkdir -p ~/.agents/skills
git clone https://github.com/zokmi/third-party-package-report-skill.git ~/.agents/skills/generating-third-party-package-report
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$HOME/.agents/skills" | Out-Null
git clone https://github.com/zokmi/third-party-package-report-skill.git "$HOME/.agents/skills/generating-third-party-package-report"
```

Codex 的個人 skill 位置為 `~/.agents/skills`，也可在專案的 `.agents/skills/generating-third-party-package-report` 安裝。安裝後請 Codex「使用 generating-third-party-package-report 盤點指定入口」；CLI／IDE 亦可用 `$generating-third-party-package-report` 明確呼叫。若未顯示新 skill，重新啟動 Codex。位置與載入方式依據 [OpenAI 官方 skill 文件](https://learn.chatgpt.com/docs/build-skills)。

兩個工具皆須能啟動獨立子代理，才能完成交付檢核；無法啟動時只保留草稿並回報 `UNAVAILABLE`。

### 更新

在對應安裝目錄執行 `git pull --ff-only`，再重新載入工具。若曾手動修改已安裝檔案，先備份並處理差異。Release 頁亦提供版本 ZIP；解壓後將含 `SKILL.md`、`assets/`、`scripts/` 的整個資料夾放至上述位置，資料夾命名為 `generating-third-party-package-report`。

## 使用

提供 `.csproj`、`.sln` 或 `package.json` 入口；Angular 請先安裝專案相依套件。以下手動指令從本 skill 根目錄執行；代理應依實際載入路徑定位腳本，從其他目錄執行時使用腳本及專案入口的絕對路徑。

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