# Third-party Package Report Plugin

透過 Claude Code／Codex 的 plugin 管理器安裝、更新與移除。盤點 .NET API 與 Angular 的第三方套件，依證據產出 Markdown 清單，交付前由獨立唯讀子代理檢核。

## 安裝前準備

需要 Git、Python 3，以及支援 plugin 和獨立子代理的 Claude Code 或 Codex。先確認 `git --version`、`python --version` 與目標工具的 `plugin --help` 可執行；不支援下列命令時先更新工具。

Marketplace：`third-party-package-plugins`；plugin ID：`third-party-package-report@third-party-package-plugins`。

以下是終端機 CLI 指令，適用 Bash／zsh 與 PowerShell。僅安裝你要使用的工具。

## Claude Code 安裝

```sh
claude plugin marketplace add https://github.com/zokmi/third-party-package-report-skill.git --scope user --json
claude plugin install third-party-package-report@third-party-package-plugins --scope user --json
```

重新啟動 Claude Code，呼叫 `/third-party-package-report:generating-third-party-package-report`，並提供 `.csproj`、`.sln` 或 `package.json` 入口。

更新：

```sh
claude plugin marketplace update third-party-package-plugins --json
claude plugin update third-party-package-report@third-party-package-plugins --scope user --json
```

移除：

```sh
claude plugin uninstall third-party-package-report@third-party-package-plugins --scope user
```

## Codex 安裝

```sh
codex plugin marketplace add https://github.com/zokmi/third-party-package-report-skill.git --ref main --json
codex plugin add third-party-package-report@third-party-package-plugins --json
```

重新載入 Codex，請它「使用 generating-third-party-package-report 盤點指定入口」；也可從 skill 選擇器選取該技能。

更新：

```sh
codex plugin marketplace upgrade third-party-package-plugins --json
codex plugin add third-party-package-report@third-party-package-plugins --json
```

移除：

```sh
codex plugin remove third-party-package-report@third-party-package-plugins --json
```

## 給 agent：安裝、更新與遷移

使用者要求安裝時，先讀目標 CLI 子命令的 `--help`，再用 `plugin marketplace list --json` 與 `plugin list --json` 查現況。已有正確來源就更新，不重複新增；每一步檢查退出碼，失敗就停止後續遷移。未指定工具時以目前工具為準，不同時安裝兩邊。

舊版 v1.0／v1.1 直接放在 `~/.claude/skills/generating-third-party-package-report` 或 `~/.agents/skills/generating-third-party-package-report` 的安裝，請在 plugin 安裝並確認載入成功後，將舊資料夾移到 skills 載入目錄外備份，避免重複技能。只處理已確認屬於本套件的舊資料夾，保留其他 skills；新版以 plugin 管理器維護，不再 clone 至 skills 目錄或以 `git pull` 更新。

## 使用與交付

Angular 請先安裝專案相依套件。代理依實際載入的 `SKILL.md` 定位同層 `scripts/` 與 `assets/`，不假設 plugin 快取位置或目前工作目錄。

- 支援 .NET API 與 Angular；收集直接參考、版本、授權中繼資料及使用證據，不展開所有遞移相依。
- .NET 沿 ProjectReference 展開；授權讀本機 NuGet 快取或 node_modules，缺漏另行查證。
- `not-found` 不等於可移除，須人工排查。
- 只列使用中的套件，固定七欄並附授權彙總，預設輸出 `docs/<範圍>-第三方套件清單.md`。
- 最終報告由唯讀子代理讀取報告及原始證據，全部適用項目 PASS 才交付；修改後重新檢核。
- 無法啟動子代理或證據不足時保留草稿並回報 `UNAVAILABLE`／`UNVERIFIED`。

## 專案結構

```text
.claude-plugin/plugin.json       Claude Code plugin manifest
.claude-plugin/marketplace.json  兩個工具使用的 marketplace
.codex-plugin/plugin.json        Codex plugin manifest
plugin.json                      可攜式 plugin metadata
skills/generating-third-party-package-report/
  SKILL.md
  assets/report-template.md
  scripts/collect_packages.py
```

Release ZIP 是完整 plugin 原始封裝；一般使用者依上述 marketplace 指令安裝。

格式參考：[Claude Code marketplace 文件](https://code.claude.com/docs/en/plugin-marketplaces)、[OpenAI plugin 文件](https://developers.openai.com/plugins/deploy/submission)。本工具協助整理授權證據，不取代個別授權條款查證。