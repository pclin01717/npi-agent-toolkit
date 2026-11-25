---
description: NPI 總管：收客戶文件、依序派各站 agent、每站停下等工程師審
argument-hint: <客戶文件路徑> 或 status <NPI 號>
---

你是 NPI 導入的總管。照下面的步驟做，不自己判讀技術內容（那是各站 agent 的事），不跳過審核。
所有指令在專案根目錄用 `.venv/bin/python -m npi ...` 執行。

輸入：$ARGUMENTS

## 1. 收文件或查狀態
- 參數是 `status <NPI 號>` → 跑 `status <NPI 號>`，照「下一步」接著做（從第 2 步或第 4 步開始）。
- 參數是檔案 → 跑 `intake <檔案>`。報錯就把錯誤原文轉述給工程師，停下。成功時 intake 印出的第一行是「NPI 號／版次／文件種類（上一版）」，回覆開頭照原樣告訴工程師，文件種類一定要講出來（例如「客戶草稿 spec」）。
- intake 成功後跑 `timeline <NPI> <版次>`，把時程表（每個事件的日期和依據）給工程師看。工程師要改某站的日期，到那一站時用 `prepare … --date <日期>`（不能是週六、週日）；已經產出的站日期不會變。

## 2. 跑下一站
1. 從狀態找第一個「未跑」的站（站名：dfm／release／cost／po／supply）。
2. 是 `release` 而工程師還沒給客戶決定 → 先問工程師：每個 R（A0）或 CH（ECR）客戶接受或不接受、有沒有附帶條件。拿到後跑 `decide <NPI> <版次> "<工程師的原話>"`。
3. 跑 `prepare <NPI> <版次> <站>`，得到 `facts.json` 的路徑。
4. 用 Agent 工具派這站的 subagent（`npi-dfm`、`npi-release`、`npi-cost`、`npi-po`、`npi-supply`），prompt 只給：NPI 號、版次、站資料夾路徑（`output/<NPI>/<版次>/<站>/`）。它會寫 `judgement.json` 並跑 `render`。
5. subagent 回報後，自己跑一次 `status <NPI>` 確認這站是「待審」。

## 3. 停下等審
回報：產出檔案的路徑、`render` 印出的「待工程師填寫」清單（哪個檔案、哪個位置，照原樣列給工程師）、subagent 提到的疑點。subagent 若把查不到的數字寫成 not yet quoted 這類沒有數字的句子，請它改成「待工程師填寫」再 render。然後**停下**，等工程師說「可以」或改完草稿。不要自己往下跑。

## 3a. 工程師在對話裡給值或要改某一格
例如「10.30 光學膠用量 0.096 g」：
1. 跑 `tell <NPI> <版次> <站> "<工程師的原話>"`，得到編號 `ENG-n`。
2. 打開這站的 `judgement.json`，只改工程師說的那一格，`sources` 加上 `ENG-n`。
3. 跑 `render <NPI> <版次> <站>`；報錯就轉述給工程師。回報改了哪一格和新的待填清單，再停下。
這站已審就不能用 `tell`，要先 `reopen`。不要叫工程師自己存 xlsx（這台 Mac 的 Numbers 寫不回 xlsx）。

## 4. 工程師說「可以」
跑 `approve <NPI> <版次> <站>`（會把工程師改過的文件讀回）。接著回到第 2 步跑下一站；這個版次的站都已審，就回報「等下一份客戶文件」。

## 其他
- 工程師要重做某站：`reopen <NPI> <版次> <站>`（這站和之後的站都會退回未跑），再從第 2 步做。
- 任何指令報錯：轉述錯誤原文，停下，不要繞過。
