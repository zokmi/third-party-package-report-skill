---
name: generating-third-party-package-report
description: Use when asked to list, inventory, or audit third-party packages, dependencies, or open-source licenses of a .NET API (NuGet, csproj, sln, Directory.Packages.props) or an Angular frontend (npm, package.json, angular.json) — e.g. 第三方套件清單、套件盤點、授權清單、資安／法遵要求列出使用的開源元件、找出沒用到可移除的套件.
---

# 產生第三方套件清單報告（.NET API／Angular）

**核心原則：每一列的版本、授權、使用狀態都要有證據；查不到就寫「待確認」，不要憑印象填。**

產出一份 UTF-8 Markdown（`.md`）報告（樣板 `assets/report-template.md`），**只列使用中的套件**，欄位固定為：#、套件、版本、授權、用途說明、使用專案、備註；表格後接「授權彙總」。

報告不放「使用狀態」欄、不列未使用／可移除／待確認的套件、不放已移除套件或異動歷程。這些分析結果寫在對話回報（第 8 步），由使用者決定是否處理；處理完重跑時，報告一樣只反映當下使用中的套件。

## 執行環境

支援 Claude Code 與 Codex，兩者使用相同的分析、Markdown 樣板與子代理檢核流程。執行前以本次實際載入的 `SKILL.md` 所在目錄作為 skill 根目錄；`scripts/` 與 `assets/` 均相對於此根目錄解析，不依賴目前工作目錄或固定的個人安裝路徑。使用當前工具提供的子代理能力執行第 7 步；無此能力時依 `UNAVAILABLE` 處理。

## 流程

1. **確認範圍**：問清楚入口（例如 `webAPI/App.Api/App.Api.csproj`、`frontend/package.json`，或兩者都要），記下分析基準（分支／commit；工作區有未提交的 csproj／package.json 修改要在報告註明）。Angular 必須已 `npm install`，否則版本與授權讀不到。
2. **跑收集腳本**（可一次給多個入口）：將 `<skill根目錄>` 替換成上述實際絕對路徑，入口與輸出路徑也使用目標專案的實際路徑。
   ```bash
   python -I "<skill根目錄>/scripts/collect_packages.py" <入口...> > "<工作目錄>/packages.json"
   ```
   輸出每個套件的 `versions`、`projects`、`category`、`meta.license`、`usage`（`status`、`files`、`byProject`、`samples`、`via`、`hint`）。`--include-first-party` 會連 `Microsoft.*`／`System.*` 一起列。
3. **補齊授權**：`license` 為 `file:<路徑>` 時讀該檔判斷；空值或 `SEE LICENSE IN ...` 時讀套件內授權檔或查 nuget.org／npmjs.com。
4. **判定使用狀態**，依 `usage` 與下表：

   | 腳本結果 | 報告狀態 |
   |----------|----------|
   | `found`，via 為 source／config／angular.json／npm scripts／tsconfig types | 使用中 |
   | `found`，via 為 implicit／peer of X／types-of-used-package | 使用中，備註寫明「X 的 peer 相依」等原因 |
   | `found`，但只出現在入口專案而套件在下游專案也有引用 | 備註「入口專案的直接參考可移除」 |
   | `not-found` | **不可直接標可移除**，先做下面的人工排查 |

   `not-found` 人工排查：
   - **.NET**：看 `hint`。DI 擴充方法類（Swashbuckle、各種 `AddXxx`）查 `Startup`／`Program`；原生庫（`*.Native.*`）跟隨包裝套件；另查反射載入、`appsettings`、`web.config`、Razor。
   - **Angular**：查 `NgModule` 字串設定、`angular.json` 的 `allowedCommonJsDependencies` 以外的用法、`index.html` 的 `<script>`／CDN、`.husky`、`proxy.conf`；後端專用套件（`koa-jwt`、`jsonwebtoken`）出現在前端通常就是可移除。
   - 都沒有 → 未使用，可移除；仍無法排除 → 待確認。
5. **風險改寫判斷**：有風險授權且用量小、或 repo 內已有同功能套件 → 列為「可改寫」，寫替代方案與用到的檔案數（放對話回報，不進報告）。
6. **填寫報告**：只填判定為「使用中」的套件（含 peer 相依、DI 擴充方法類、跟隨包裝套件的原生庫）。分節規則寫在樣板註解（Angular 依 `category` 分執行期／框架／開發工具三節）。存成 `docs/<範圍>-第三方套件清單.md`（無 docs 目錄就問）。
   - 用途說明寫業務用途（「Excel 匯入匯出」），不要抄套件描述。
   - 備註只寫使用中套件本身的事實：版本鎖定原因與勿升版警示（例：2.x 起改付費授權）、授權風險、停止維護、經由哪個專案間接取得。不寫單號或「由 X 取代」這類異動歷程。
   - 「授權彙總」依授權分列套件數與一句說明；「需付費的商業授權」一列即使為 0 也保留。
   - 因鎖版本或修補漏洞而加入、但屬平台原廠的套件（`Microsoft.*`／`System.*`），在表格後以一行附註列出，不進主表。
7. **產出後派子代理檢核（交付前必做）**：報告寫入後，啟動獨立唯讀子代理，提供最終 `.md` 路徑、入口／分析基準、`packages.json`、逐項使用證據與授權來源。子代理須實際讀取報告及原始證據，不得只看主代理摘要；不得修改報告、原始碼或證據。
   - 逐項核對：副檔名及內容確為 Markdown、七欄與分節正確、只列使用中套件、範圍完整、版本／授權符合實際使用版本、用途與使用專案有依據、授權彙總與主表一致（含合併列的套件數）、商業授權列即使為 0 仍保留、風險與平台原廠附註符合規則。
   - 子代理回傳「檢核項目｜報告位置｜原始證據｜PASS／FAIL／UNVERIFIED｜缺漏與修正方式」及整體結論。證據不足為 `UNVERIFIED`；無法啟動子代理為 `UNAVAILABLE`。只有全部適用項目 `PASS` 才可交付並宣稱完成。趕時間也不得省略；其他結論保留本機草稿、回報缺口，不以主代理自審代替。
   - 修正報告後重新派子代理複審；報告、套件清單、分析基準或證據有變動時，舊 `PASS` 失效，須針對最終版本重審。
8. **回報（對話中，不寫進報告）**：未使用可移除、待確認、可改寫、授權風險、停止維護、版本衝突（`versionConflict`）各幾項，逐項附證據；一併提供最終 `.md` 檔案路徑與子代理檢核結論。

## 需要標示風險的授權與狀況

| 類型 | 例子 | 備註寫法 |
|------|------|----------|
| 非商業／付費授權 | EPPlus 5+（PolyForm Noncommercial）、SixLabors ImageSharp 3.x（Split License）、CKEditor 4 LTS、Highcharts | 寫商業使用門檻與可替代套件 |
| Copyleft | GPL、AGPL；LGPL（tinymce 4–6、heic-to、libheif） | 前端打包會散布原始碼給瀏覽器，LGPL 也要標註 |
| 包裝套件與原生庫授權不同 | `*.Native.*`、wkhtmltopdf、libheif | 分別寫包裝與原生庫授權 |
| 停止維護或已棄用 | wkhtmltopdf、`meta.deprecated` 有值、Angular 已 EOL 的大版本 | 寫替代方案 |

同一套件的授權會隨大版本改變（ImageSharp 2.x 為 Apache-2.0、3.x 改 Split License），一律以**實際使用的版本**判斷。風險在 Markdown 的授權或備註儲存格以 `**風險：原因**` 標示。

## 常見錯誤

- 只看單一 csproj → 腳本會沿 ProjectReference 遞迴，入口給 API 專案或 .sln。
- 把 nuspec `licenseUrl`（`aka.ms/deprecateLicenseUrl`）當授權 → 讀授權檔。
- 腳本 `not-found` 直接寫「可移除」→ 先做人工排查。
- Angular 只看 `import` → styles／scripts 在 `angular.json`、CLI 在 npm scripts、型別在 tsconfig，腳本都已涵蓋，報告要寫出依據。
- 報告沿用舊版本號 → 每次重跑腳本，以目前工作區為準並寫明基準。
- 把未使用、待確認或已移除的套件寫進報告，或加「使用狀態」「異動」欄 → 報告只列使用中，分析結論放對話回報。

- 交付 HTML、僅將 HTML 改副檔名、或未經子代理 PASS 就交付 → 依 Markdown 樣板產出並完成最終版本複審。
