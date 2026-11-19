# 工作項目與獨立驗收

`[x]` 完成；`[ ]` 未完成；環境阻擋的驗證保留未勾選。

## Phase 1 — 初始化

- [x] P1-01 檢查本機／遠端／工具，建立 feature branch；無 commit/push/merge。
- [x] P1-02 建立七份規格、架構邊界、驗收與風險文件。
- [x] P1-03 FastAPI 設定、存活／資料庫 readiness 及一般錯誤回應。
- [x] P1-04 React / TS / Vite / Tailwind / Framer Motion 繁中基礎頁面，實際呼叫 API。
- [x] P1-05 SQLAlchemy model、Alembic 初始 game_types 與停用目錄。
- [x] P1-06 Dockerfile、PostgreSQL named volume、migration job、Nginx 與 healthcheck 設定。
- [x] P1-07 Pytest、Ruff、Mypy、TS、ESLint、Playwright 設定與鎖定相依。
- [ ] P1-08 基礎環境完整驗收（整體仍未完成）。
- [x] P1-08a 官方 Compose 工具 config --quiet 解析成功；不等同容器驗收。
- [x] P1-08b 原生 PostgreSQL migration 往返、UUID／UTC、約束、交易回滾與 readiness。
- [x] P1-08c 原生 PostgreSQL 停止／重啟、資料保留與真實 HTTP API 重新連線。
- [ ] P1-08d Docker build/up、Nginx 代理、容器健康／named volume／容器重啟（缺 Docker engine）。
- [x] P1-09 執行本機可用檢查並在報告記錄精確結果。
- [x] P1-10 交付報告、Phase 2 計畫與建議 commit；停止等待確認。

目前狀態：**程式初始化完成，基礎環境部分驗收**。
持續限制：不安裝 Docker Desktop、不啟用 WSL、不改 Windows 設定；
不 commit/push/merge/rebase、不建立 PR、不改 Git 身分。
P2-A 驗收為 CONDITIONAL PASS；P2-B 經 R2 修補與人工驗收為 CONDITIONAL PASS，核准純型別階段結案
（保留條件見 `docs/reports/PHASE_2.md`）。P2-C 契約階段已結案；P2-D 機制階段已結案；P2-E 五張牌型階段已結案；P2-F 階段已結案；Phase 2 已由人工決議以 CONDITIONAL 方式收尾（見 PHASE_2.md），Phase 3 尚未開始。

## Phase 2 — 共用核心（P2-B～P2-F 已結案；Phase 2 以 CONDITIONAL 收尾）

- [x] P2-01（P2-A）Card／Rank／Suit 值型別；驗收 52 張唯一牌、序列化往返、拒絕非法牌。
- [x] P2-02（P2-A）Deck／安全 Shuffle／發牌／剩餘數／重置；固定牌序注入有 test-only 標記。
- [ ] P2-03 Player／Room／Session／Event／Result 型別與不可變動作；驗收狀態及事件版本。（部分完成：Room、GameSession 延後，規格未定義欄位契約）
- [x] P2-04 GameEngine Protocol 六個方法與 registry；驗收重複及未知引擎錯誤。（P2-C、P2-D 已結案）
- [x] P2-05 五張德州牌型純函式／比較測試；驗收所有牌型、wheel、踢腳、平手及不依賴花色。（P2-E 已結案）
- [x] P2-06 隱藏資料投影契約及十三支介面擴充測試；不可啟用未實作遊戲。（P2-F 已結案，CONDITIONAL PASS）
- [x] P2-07 核心測試／型別／品質檢查、報告、更新任務及建議 commit。（Phase 2 以 CONDITIONAL 方式收尾；P2-03 的 Room／GameSession 延後，風險總表見 PHASE_2.md）

### 分批驗收對照

- [x] P2-A-01 唯讀盤點 Git／未提交成果、七份規格及 Phase 1 基準。
- [x] P2-A-02 不可變 Card、標準 52 張 Deck、安全預設及明確測試牌序工廠。
- [x] P2-A-03 核心 127 項測試；含 Phase 1 的完整回歸 136 passed／0 skipped；Mypy／Ruff 通過。
- [x] P2-A-04 新增 `docs/reports/PHASE_2.md`，交付後停止，等待人工驗收。
- [x] P2-B：純型別契約結案（人工驗收 CONDITIONAL PASS，經 R1／R2 修補；歷史 FAIL 紀錄保留）。不含正式認證、玩家投影、遊戲引擎或正式發牌。
- [x] P2-C：六方法引擎 Protocol、結果型別、牌組來源規則與契約測試；人工驗收 CONDITIONAL PASS，契約階段結案（保留條件見 PHASE_2.md）。不含真實引擎、玩家投影、認證或正式發牌。
- [x] P2-D：EngineRegistry（重複／未知 code 錯誤、未登記即不可用、無 enabled 旗標）；人工驗收 CONDITIONAL PASS，Registry 機制階段結案（保留條件見 PHASE_2.md）。目前無真實引擎，Registry 實際為空。
- [x] P2-E：德州五張牌型純函式與比較（wheel、踢腳、平手、不依賴花色）；人工驗收 CONDITIONAL PASS，五張牌型階段結案（保留條件見 PHASE_2.md）。不含七選五、結算、真實引擎、玩家投影或正式發牌。
- [x] P2-F：投影工具、共用引擎契約測試套件、十三支擴充性驗證與 Phase 2 對帳／風險總表；人工驗收 CONDITIONAL PASS，P2-F 階段結案（保留條件見 PHASE_2.md）。

P2-A 不代表整個 Phase 2 完成；P2-07 仍需全階段功能到齊後才可勾選。
P2-03 整體尚未完成：GameEvent／GameResult 已於 P2-C 實作，Room／GameSession 型別仍未實作（延後）。
（P2-A 當時的限制，已由後續階段更新）本輪不實作 P2-C～P2-F，不接入正式發牌，不變更 Phase 1 migration 或 card.py／deck.py。

### P2-A 持續開放事項（不得視為 P2-B 已解決）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險。
- [ ] test-only Deck 與正式引擎的隔離。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口。

### P2-B 本輪驗收

- [x] P2-B-01 唯讀核對規格／未提交成果／既有型別及最小內部契約。
- [x] P2-B-02 純資料型別、必要欄位驗證及公開／私有結構分離。
- [x] P2-B-03 P2-B 124 passed、P2-A 127 passed、無 DB 健康檢查 3 passed；Mypy／Ruff 通過。
- [x] P2-B-04 `PHASE_2.md` 與 `P2_B_TEST_EVIDENCE.json` 記錄分支／無 HEAD／SHA256／時間／環境／輸出；停止等待人工驗收。

### P2-B-R1 公開資料隔離修補

- [x] P2-B-R1-01 唯讀核對／重現 PlayerWithHand 的 asdict 與 repr 洩漏；比較拒絕子類別與 DTO 轉換。
- [x] P2-B-R1-02 精確公開模型型別拒絕；保留一般 Player 及原有合法資料的參照／輸出。
- [x] P2-B-R1-03 R1 19／原 P2-B 124／P2-A 127／健康檢查 3 項均通過，合計 273 passed、0 failed、0 skipped；Mypy／Ruff 通過。
- [x] P2-B-R1-04 `P2_B_R1_TEST_EVIDENCE.json` 與 PHASE_2 修補報告完成；原始證據未覆寫，停止等待人工複驗。
- [x] P2-B-R1-05 人工複驗已發現 DisplayNameWithHand 洩漏（R1 不足），由 R2 接續。

### P2-B-R2 公開資料邊界完整修補

- [x] P2-B-R2-01 唯讀盤點公開欄位矩陣；重現 DisplayNameWithHand 被接受並保留私有屬性。
- [x] P2-B-R2-02 所有公開欄位值改精確型別驗證（str／UUID／int／tuple／Enum），PublicGameData 重驗 Player／Turn 欄位。
- [x] P2-B-R2-03 新增 25 項對抗測試；R2 25／R1 19／P2-B 124／P2-A 127／健康檢查 3 合計 298 passed；Mypy／Ruff／format／pip check 通過。
- [x] P2-B-R2-04 `P2_B_R2_TEST_EVIDENCE.json` 與 PHASE_2 報告完成；R1／原始證據未覆寫。
- [x] P2-B-R2-05 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P2-B 純型別階段結案（保留條件見 PHASE_2.md）。

### P2-C 六方法 GameEngine Protocol

- [x] P2-C-01 規劃與 6 項決策確認（照建議）。
- [x] P2-C-02 `engine_types.py` 新結果／事件型別，精確型別驗證。
- [x] P2-C-03 `engine.py` Protocol 與 `require_production_deck`。
- [x] P2-C-04 28 項契約測試；完整 backend 327 passed、5 skipped；Mypy／Ruff／format／pip check 通過。
- [x] P2-C-05 `P2_C_TEST_EVIDENCE.json` 與 PHASE_2 報告完成；停止等待人工驗收。
- [x] P2-C-06 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P2-C 契約階段結案（保留條件見 PHASE_2.md）。

### P2-D Engine Registry

- [x] P2-D-01 規劃與 5 項決策確認（照建議）。
- [x] P2-D-02 `registry.py`：EngineRegistration／EngineRegistry，精確型別驗證與執行期方法檢查。
- [x] P2-D-03 34 項測試；完整 backend 361 passed、5 skipped；Mypy／Ruff／format／pip check 通過；10 種變異全被抓到。
- [x] P2-D-04 `P2_D_TEST_EVIDENCE.json` 與 PHASE_2 報告完成；停止等待人工驗收。
- [x] P2-D-05 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P2-D 機制階段結案（保留條件見 PHASE_2.md）。

### P2-E 德州五張牌型

- [x] P2-E-01 盤點與決策確認（照建議）。
- [x] P2-E-02 `texas_holdem/hands.py`：HandCategory／HandRank／evaluate_five／compare。
- [x] P2-E-03 52 項測試與組合數 oracle；完整 backend 413 passed、5 skipped；一次性窮舉 2,598,960 手與公認數字相符。
- [x] P2-E-04 `P2_E_TEST_EVIDENCE.json` 與 PHASE_2 報告完成；停止等待人工驗收。
- [x] P2-E-05 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P2-E 五張牌型階段結案（保留條件見 PHASE_2.md）。

### P2-F 投影、契約套件與整體對帳

- [x] P2-F-01 規劃與 5 項決策確認（照建議）。
- [x] P2-F-02 `projection.py`：project_player_view／events_for_viewer，15 項測試、10 種變異全被抓到。
- [x] P2-F-03 `engine_contract_suite.py`：可重用契約套件；13 種故意寫壞的引擎全被抓到。
- [x] P2-F-04 十三支擴充性（不同 payload 型別）與未登記不可啟用測試；無十三支規則。
- [x] P2-F-05 完整 backend 445 passed、5 skipped；`P2_F_TEST_EVIDENCE.json`、Phase 2 對帳與風險總表完成；停止等待人工驗收。
- [x] P2-F-06 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P2-F 階段結案（保留條件見 PHASE_2.md）。Phase 2 已另行決議收尾。

## Phase 3 — 德州撲克

- [x] P3-00 前置加固（Deck 失敗關閉、test-only 靜態守衛、契約套件三項缺口、`HandRank` 語意驗證、公開資料／事件 payload 擴充機制）：人工驗收 CONDITIONAL PASS，P3-00 階段結案（保留條件見 PHASE_2.md；其中前三項須在 P3-01 前處理）。不含德州狀態、盲注、下注、邊池或引擎。
- [x] P3-00-A 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P3-00 階段結案。P3-01 尚未開始，須使用者另行授權，且須先提供盲注金額、初始積分與燒牌設定。
- [x] P3-01-0 處理 P3-00 前三項保留條件（擴充資料與措辭變體洩漏偵測、擴充欄位矩陣強制、共用驗證函式）：人工驗收 CONDITIONAL PASS，隨 P3-01 一併結案（措辭偵測仍為啟發式，見 PHASE_2.md）。
- [x] P3-01 2～9 人建局與盲注／按鈕；單挑與輪替：`TexasRules`、座位與盲注位置、`TexasPublic`、`start_hand` 人工驗收 CONDITIONAL PASS，建局階段結案（保留條件見 PHASE_2.md；其中狀態不變式缺口須在 P3-02 動手前處理）。盲注金額、籌碼、燒牌的正式值仍待提供。不含玩家動作、各街、下注、邊池、結算或引擎。
- [x] P3-01-A 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P3-01 階段結案。P3-02 尚未開始，須使用者另行授權。
- [x] P3-02 各街狀態機與合法動作（棄牌、過牌、跟注、不足額 all-in）；全棄牌與全 all-in：`TexasEngine`、街推進、事件 payload；人工驗收 CONDITIONAL PASS，階段結案（保留條件見 PHASE_2.md；其中建局不一致建議在 P3-03 前統一）。bet、raise、超額 all-in 屬 P3-03。不含結算、Registry 登記或完整契約。
- [x] P3-02-0 擴充一致性檢查（核心契約變更，處理 P3-01 保留條件 1）：人工驗收 CONDITIONAL PASS，隨 P3-02 一併結案。
- [x] P3-02-A 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P3-02 階段結案。P3-03 尚未開始，須使用者另行授權。
- [x] P3-03 最小加注、短額 all-in、重新開放下注；錯誤不改狀態：bet、raise、all-in 規則（加到金額、累計式重新開放）與建局時一輪無須行動的統一處理；人工驗收 CONDITIONAL PASS，階段結案（保留條件見 PHASE_2.md；其中測試覆蓋缺口建議補強）。不含七選五、邊池、結算、未被跟注部分的退回或 Registry 登記。
- [x] P3-03-A 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P3-03 階段結案。P3-04 尚未開始，須使用者另行授權。
- [x] P3-04-0 只加測試的補強（多組盲注、棄牌與 all-in 對手情境）：人工驗收 CONDITIONAL PASS，隨 P3-04 一併結案。
- [x] P3-04 七選五、邊池／平分／退回與奇數籌碼；驗收積分守恆：`best_of_seven`、攤牌亮牌、結算純函式、`calculate_result` 已實作，並以暴力 oracle 與兩份獨立代理參考驗證；人工驗收 CONDITIONAL PASS，階段結案（保留條件見 PHASE_2.md；其中契約政策需人工再確認、窮舉與變異腳本不在 repo）。不含 Registry 登記、Room、認證、傳輸層或結算的公開／套用機制。
- [x] P3-04-A 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P3-04 階段結案。P3-05 尚未開始，須使用者另行授權。
- [x] P3-05 完整固定牌序牌局及視圖隔離；測試／報告：依授權，本階段範圍為 Registry 登記機制、完整規則契約（含追溯測試）、結算的套用／公開／事件整合與回歸；人工驗收 CONDITIONAL PASS，階段結案（保留條件見 PHASE_2.md）。實際登記與結算明細公開被未確認政策阻擋，已停止並列出待確認事項。
- [x] P3-05-A 人工獨立複驗完成；決議 CONDITIONAL PASS，核准 P3-05 階段結案。P3-06 尚未開始，須使用者另行授權。

## Phase D — 大老二私人原型（D1 契約，規則版本 `taiwan-four-v1`）

- [x] PD-01 引擎、記憶體私人房間原型與前端（提交 `e0865def`）；分支 CI 通過。
- [x] PD-02 唯讀審查：對照 D1 R01～R13 與補遺，未發現阻擋缺陷，建議通過（審查結論，非人工核准）。
- [x] PD-03 補強整合測試與獨立牌型 oracle 測試、驗收報告 `docs/reports/PHASE_D.md`。
- [ ] PD-04 人工驗收與合併（Draft PR #6；strict Mypy 目前不在 CI，見報告「已知限制」）。

Phase D 的規則為固定四人，與下方 Phase 4 的「2～4 人」描述不同。Phase 4 四項維持未勾選，
是否改寫或由 Phase D 取代，須人工決定。

## Phase 4 — 大老二

- [ ] P4-01 集中規則設定與 rules_version；全部地方規則決策可測。
- [ ] P4-02 單／對／三／五張辨識與比較；邊界牌型矩陣測試。
- [ ] P4-03 2～4 人發牌、首出、輪次／Pass 重置／結束；測試完整牌局。
- [ ] P4-04 拒絕非法牌與越權手牌；完整測試／型別／報告。

## Phase 5 — 多人連線

- [ ] P5-01 其餘八表 migration、FK／索引與約束；PostgreSQL 往返驗證。
- [ ] P5-02 真實認證與 session；測試登入／撤銷／錯誤／限流。
- [ ] P5-03 房間邀請／座位／準備／開局；測試非成員與座位競態。
- [ ] P5-04 WS 認證／Origin／逐人視圖；雙玩家與惡意第三者測試。
- [ ] P5-05 行鎖／版本／request_id／唯一序號與結算交易；併發重送不重複扣分。
- [ ] P5-06 重連／重播／快照恢復／歷史統計；測試隱私與中斷恢復。
- [ ] P5-07 斷線逾時策略／錯誤／速率限制；測試／報告。

## Phase 6 — 前端

- [ ] P6-01 首頁／登入／大廳／建房，全部操作連真實 API。
- [ ] P6-02 等待室／座位／準備／開局，處理權限及錯誤。
- [ ] P6-03 德州桌與動態下注操作、版本同步及重送。
- [ ] P6-04 大老二桌與選牌／Pass，依 game_type 呈現。
- [ ] P6-05 個人資料／紀錄、桌面／手機與減少動畫設定；可及性驗證。
- [ ] P6-06 真實多 browser context E2E／型別／品質／報告。

## Phase 7 — 整合部署

- [ ] P7-01 全系統整合與 Postgres 真實競態／交易測試。
- [ ] P7-02 越權、過期、重送、Origin、限流、隱藏牌與日誌安全測試。
- [ ] P7-03 桌面／手機瀏覽器矩陣 E2E，記錄實際裝置與模擬範圍。
- [ ] P7-04 Docker 部署／TLS／秘密管理／依賴檢查。
- [ ] P7-05 pg_dump/restore 與事件重播恢復；量測 RPO/RTO。
- [ ] P7-06 定義並實測多人負載及延遲；正式驗收報告與限制。
