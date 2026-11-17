# Phase 2 進度報告

## P3-05 Registry 登記機制、完整規則契約、結算套用與公開 — 正式結案決議 CONDITIONAL PASS（僅文件更新）

人工驗收決議：P3-05 = **CONDITIONAL PASS**，核准 **P3-05 階段**結案。本節同時是 P3-05 的階段報告（實作內容、結果與限制）。
本次文件更新只動 `TASKS.md`、本檔、`docs/TEXAS_HOLDEM_CONTRACT.md`（更正來源行號）並新增 `P3_05_TEST_EVIDENCE.json`；
未修改任何程式或測試，未開始 P3-06，未做任何 Git 寫入。注意：P3-05 的實作與文件尚未提交。

### 授權範圍與阻擋處理

授權範圍：Registry 登記、完整規則契約、P3-04 結算結果的公開／套用／事件整合、測試與回歸。依指示，**未確認的政策沒有被補完**：
政策不阻擋的部分已完成；依賴政策的部分已停止，列在「需要使用者確認」。未實作 Room、認證、傳輸層、完整多人流程、前端；沒有任何 PostgreSQL 假通過標記（仍是 5 項 skipped）。

### 修改與新增的檔案

- 修改：`texas_holdem/__init__.py`、`engine.py`（`settle_hand`）、`events.py`（`HandSettled`）、`settlement.py`（`apply_settlement`）、`state.py`（`SeatState.payout`、`TexasPublic.settled` 與不變式）、`tests/games/test_texas_setup.py`（只補欄位矩陣項目並加強一個斷言，**沒有放寬任何既有斷言**，沒有刪除或改名任何既有測試）。
- 新增：`texas_holdem/registration.py`、`tests/games/test_texas_registry.py`、`test_texas_settlement_apply.py`、`test_texas_contract_traceability.py`、`docs/TEXAS_HOLDEM_CONTRACT.md`、`docs/reports/P3_05_TEST_EVIDENCE.json`。

### Registry 契約與結果

- `texas_registration(rules)` 與 `register_texas_holdem(registry, rules)`：代碼固定為 `texas_holdem`，人數範圍 2 到 9 與 `game_types` 目錄一致（測試直接解析 migration），規則版本取自規則物件。
- 重複登記與未知代碼以 `GameError` 回傳、不覆蓋、不回顯輸入；沒有全域 Registry、沒有預設登記或預設規則；應用程式碼只有 `registration.py` 直接建構 `TexasEngine`（靜態檢查），沒有繞過 Registry 的硬編碼。
- 既有 `GameEngine` 介面未破壞（`settle_hand` 是額外方法，不在六方法內）。
- 10 項測試；變異驗證（代碼、規則版本、人數範圍、規則型別檢查、引擎使用的規則）全部被抓到。
- **機制完成，實際登記未完成**：專案沒有啟動組裝處，且正式規則值（盲注、燒牌）尚未核准，所以目前沒有任何地方真正登記。

### Texas Hold'em 完整規則契約

`docs/TEXAS_HOLDEM_CONTRACT.md`：條款表（ID、條款、來源、狀態、測試）。狀態分 SPEC（規格明寫）、APPROVED（專案紀錄中已批准）、CHOSEN（規格未定義的實作選擇，待人工確認）、OPEN（無政策）。
`test_texas_contract_traceability.py` 解析條款表：編號唯一、狀態合法、每個非 OPEN 條款指向的測試真實存在、OPEN 條款不得宣稱有測試、必要主題（牌組、座位、按鈕、盲注、燒牌、各街、動作、主池邊池、退回、合併、平手與奇數籌碼、名次、亮牌、結算與守恆、套用、Registry）皆有條款。
**追溯測試只證明測試存在，不證明語意對應；** 複驗抽查約 10 項相關。五項未確認政策各有「既有依據、缺口、候選、程式影響、是否阻擋」的分析（見該文件第三節）。

### 結算的套用、公開與事件流程

1. 牌局結束後（`FINISHED`）：`settle_state` 只計算，不改狀態。
2. 驅動牌局的伺服器端呼叫 `TexasEngine.settle_hand(state)`（內部 `apply_settlement`）：金額**一律由狀態重新計算，沒有接收外部結算的參數**；每座位 `stack` 加上 `payout`（退回加獲得）、`all_in` 改為「籌碼為 0」；`settled` 為真；狀態版本加一；發出一個**不帶任何明細**的 `HandSettled` 事件。
3. 第二次呼叫回傳 `already_settled`，直接呼叫 `apply_settlement` 拋 `ValueError`；狀態不變。
4. 由 `TexasPublic` 強制的不變式：`payout` 之和等於 `pot`；`stack` 等於 `Player.points − committed + payout`；總籌碼等於起始總積分；棄牌座位 `payout` 為 0；未結算時 `payout` 全為 0；未結束的牌局不能標為已結算。
5. 事件順序：…、`HandEnded`，然後（另一步）`HandSettled`，整手牌序號無缺口。
6. 公開範圍（現況）：`payout`、`stack`、`settled`（皆可由公開狀態推導，不新增揭露）與亮牌者的底牌；**其餘結算明細不公開（政策 5，OPEN）**。

### 測試與證據

- 新增 33 項：Registry 10、結算套用 14（套用一次、防重複、守恆、事件順序、不一致的結算無法建構、結算後視圖隔離、300 局隨機對局與獨立實作比對）、契約追溯 9。
- 完整 backend **698 passed、5 skipped**（665＋33；複驗連跑 3 次相同；5 項 skipped 皆為 `TEST_DATABASE_URL` 未設定）。
- P3-05 registry：exit 0；10 passed in 0.41s
- P3-05 settlement apply：exit 0；14 passed in 3.02s
- P3-05 contract traceability：exit 0；9 passed in 0.77s
- P3-04 settlement：exit 0；22 passed in 9.84s
- P3-04 seven-card：exit 0；31 passed in 3.50s
- P3-04-0 blinds：exit 0；13 passed in 0.35s
- P3-03 texas raising：exit 0；19 passed in 1.48s
- P3-02 texas engine：exit 0；30 passed in 6.55s
- P3-01 texas setup：exit 0；60 passed in 0.51s
- P3-00 extensions：exit 0；21 passed in 0.13s
- P3-00 deck failure and isolation：exit 0；7 passed in 1.12s
- P2-F projection：exit 0；15 passed in 0.13s
- P2-F contract suite：exit 0；31 passed in 0.83s
- P2-E texas hands：exit 0；55 passed in 3.26s
- P2-D registry：exit 0；34 passed in 0.15s
- P2-C engine contract：exit 0；28 passed in 0.16s
- R2 public field matrix：exit 0；25 passed in 0.11s
- R1 public isolation：exit 0；19 passed in 0.12s
- Original P2-B regression：exit 0；124 passed in 2.21s
- P2-A regression：exit 0；127 passed in 0.22s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.93s
- Mypy：exit 0；Success: no issues found in 56 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；63 files already formatted
- Full backend suite：exit 0；698 passed, 5 skipped, 1 warning in 33.06s
- pip check：exit 0；No broken requirements found.

- 證據檔 `P3_05_TEST_EVIDENCE.json`（來源雜湊、環境、命令、退出碼）；`registration.py` SHA-256 `4aa1183b86d5c7384a892124c6f0ec6f38d96e38aba1d0253fe4fa0592a4e073`；`settlement.py` `576af8be4d3e9b95b9b3ff6eed146ea3cf802a26a1554bd2980a290bad61d911`；`state.py` `24801d4947f5a1e7bc991d8f47496b4418a83473ffc678637b0d76df14d916bc`；契約文件 `e26dc707c75677212150e64a153866e0af05aaa5be1059eab20c69f034673aac`。
  先前各階段證據未覆寫；舊證據檔的 `git_head: null` 註記仍過時，本檔已改記錄基準 commit `c6ccf86`。
- 複驗另做、腳本不在 repo、僅記錄結果（`manual_checks_not_in_repository`）：與 `cf78553`、`c6ccf86` 兩個基準各跑 3000 局共 19,024 個狀態，行為軌跡雜湊**完全相同**；
  3000 局隨機牌局的 `settle_hand` 與第四種結算實作加獨立代理參考逐一一致（含 256 局建局即結束、1264 局有退回、2448 局有邊池、834 局有平手）；
  反射竄改（投入額、籌碼、`payout`、`settled`、`pot`）皆被拒絕（反射設定 `settled=True` 時回傳 `already_settled`，屬同程序信任限制）；22 種變異全部被抓到（其中 5 種第一次因字串不符沒有實際執行，已用正確字串補跑）。

### P3-03／P3-04 回歸

保留全部既有測試（665 項原樣通過，沒有放寬或刪除）；betting 行為軌跡與兩個基準完全相同；`SeatState`、`TexasPublic`、事件的新欄位皆有預設值，既有建構方式不受影響。

### 複驗結果與本次文件更正

- 獨立性限制：複驗由 P3-05 的作者自己執行，**規則契約的文字與政策判斷仍需人工或不熟悉本案的審查者確認**。
- 已更正：契約文件來源行號（R2.1、R2.4、R3.1、R5.1、R6.1、R6.2 各差一行；R2.4 的整數來源改為 GAME_RULES l.13；R6.9 的 SECURITY l.19 實為日誌規範，已改註）；R2.4 不再以 PRD 作為「整數」來源；R11.1 改為 DATABASE l.9–10；「不接受外部結算」自 R9.2（CHOSEN）拆出為新條款 R9.8（SPEC，SECURITY l.17）；驗收文件與證據檔已補齊。
- 【確認】Registry 機制、結算套用與防重複、籌碼守恆、資訊隔離、回歸、階段隔離。【推論】追溯測試與條款的語意對應（抽查）。
  【無法驗證】結算明細公開、真實的正式登記、API 序列化（沒有 API）、PostgreSQL。

### 保留條件

1. **牌局結束與套用結算分成兩步**：呼叫端漏掉第二步時，`calculate_result` 仍給淨變動，但狀態中的籌碼不更新；通用契約套件不知道這一步，無法強制。Phase 5 整合時必須處理；契約 R9.2 到 R9.6 為 CHOSEN，須人工確認是否改為牌局結束同一步自動套用（會改變既有的最後事件順序與測試）。
2. `register_texas_holdem` 回傳 `GameError | None`，呼叫端可忽略重複登記錯誤（同 P2-D 條件）。
3. `SeatState.all_in` 結算後語意為「籌碼為 0」；結算後的籌碼尚未銜接到下一手牌（沒有以本手結果開下一手的輔助）。
4. 在政策 5 未決下，仍實作了內容為空的 `HandSettled` 標記、`payout` 欄位與兩步結算；皆標為 CHOSEN，可被推翻。
5. 追溯測試只驗證測試存在；`test_registration_helpers_have_exactly_the_documented_signatures` 的最後一個斷言寫法偏弱。
6. P3-04 的保留條件（契約政策再確認、窮舉與變異腳本不在 repo、輸入驗證的小缺口等）與 P3-03 的六項保留條件**不因此結案而解除**。

### 需要使用者確認（阻擋的部分已停止）

1. 政策 1、2：燒牌的核准值、盲注數值與設定位置。**阻擋正式組裝（啟動時建立 Registry）。**
2. 政策 5：結算明細公開範圍（A 維持現況；B 加上各池金額、資格與得主；C 再加上牌型名稱）與公開時機；**阻擋事件內容與池明細公開。**
3. 政策 4：確認維持「合併相鄰同資格層後再分配」。
4. 政策 3：籌碼最小單位。
5. 兩步結算的設計是否符合預期（保留條件 1）。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險：P3-00 已修補並通過複驗，是否正式標為已解決由人工決定。
- [ ] test-only Deck 與正式引擎的隔離：僅緩解，仍開放。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制：仍開放。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口：仍開放。

### 尚未驗收（P3-05 通過不代表已完成）

- Room、GameSession、認證與授權、傳輸層、完整多人連線流程、前端遊戲操作流程。
- 正式組裝與實際登記（需要核准的規則值）；結算明細的公開；PostgreSQL 測試（5 項 skipped）。

---

## P3-04 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P3-04 = **CONDITIONAL PASS**，核准 **P3-04 階段**（七選五、攤牌亮牌、邊池結算與結果，含 P3-04-0 測試補強）結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P3-05，未做任何 Git 寫入。
注意：P3-04 的實作與文件尚未提交。

### 驗收範圍與獨立複驗結果

- 範圍：`settlement.py`、`hands.best_of_seven`、`TexasPublic.showdown` 與 `ShownHand`、`betting.advance` 的亮牌、`engine.calculate_result`，以及相關測試與兩份獨立參考。
- **獨立性限制（須明確記錄）**：複驗由 P3-04 的作者自己執行，不是第三方。已用新方法降低偏差，但**契約文字本身由作者撰寫，無法由這次複驗背書**，須由人工或不熟悉本案的審查者確認。
- Backend：**665 passed、5 skipped**（複驗連跑 4 次相同）；Mypy、Ruff（僅檢查）、格式檢查、`pip check` 通過；證據檔 45 個來源雜湊與 23 項檢查退出碼皆吻合。
- 結算：四種寫法不同的實作（引擎、逐籌碼層級暴力、獨立代理參考、複驗新寫的「反覆剝除最小投入」）在 180,159 組新的可達輸入（新種子、2 到 9 座位、投入最大 1000；其中 123,522 組有多個池、123,193 組有並列）完全一致；
  測試內的小桌窮舉實際為 105,168 種；400 局隨機完整牌局的 `calculate_result` 與「獨立評估器加獨立結算」逐一相符。
- 七選五：`best_of_seven` 取 21 個五張組合的最大值；全部 2,598,960 手五張牌的窮舉在 `_validate` 重構後仍完全相符（49 秒）；
  九種七張牌型數量由獨立代理的評估器與引擎各自算出，皆與公認值一致（**點數多重集合乘同花點數集合、組合數加權的類別窮舉，共 190,346 個代表手牌，不是逐一枚舉全部 133,784,560 手**）。
- 資訊隔離（3000 局探測）：中途狀態不亮牌；攤牌時恰好公開所有未棄牌座位的真實底牌；只剩一人時不亮牌；棄牌者的牌從未公開；視圖只含自己的底牌加已公開的牌；事件 payload 從未含底牌。
- 回歸：以 `cf78553` 為基準，3000 局隨機對局共 19,024 個狀態的行為軌跡（除 `showdown` 外的全部欄位、私有牌、事件）與目前版本**雜湊完全相同**。
- 合併規則的實際影響：在 123,450 組有爭奪的桌子中，合併規則改變某人結果的占 2.60%（3,212 組）。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件

1. **契約政策需人工再確認**：合併相鄰同資格層、退回定義、餘數順序、按鈕最後、亮牌全部未棄牌座位、競賽名次。
   獨立代理只驗證「實作符合契約文字」；其案例無法分辨合併與否，合併規則只由作者手算範例支撐。
2. **證據可重現性**：精確窮舉腳本（引擎端與代理端）與 27 種變異的清單與輸出只存在暫存目錄，不在 repo；證據檔只記錄結果。
3. **文字更正**：`PHASE_2.md` 的 P3-04 章節以「窮舉…涵蓋全部 133,784,560 手」描述類別加權計算，應理解為上述 190,346 個代表手牌；
   「另 6000 組隨機」實際比對 4,364 組（不可達輸入被跳過，測試未斷言最少數量）；「超過 4 萬種」實際為 105,168 種。
4. **輸入驗證**：`settle`／`odd_chip_order` 不驗證 `button`；有爭奪的池遇到非整數 `button` 會拋 `TypeError`，無爭奪時靜默接受。
   `best_of_seven` 含 `assert best is not None`（`python -O` 下被移除，實務不可達）；`calculate_result` 遇異常或不可達狀態會拋例外而非回傳 `GameError`（可達狀態未觸發）。
5. **證據檔**：`P3_04_TEST_EVIDENCE.json` 的 `git_head: null` 與「No commits exist」註記已過時，未記錄基準 commit `cf78553`。
6. **結算的呼叫端風險**：`calculate_result` 只回傳淨變動，狀態的 `pot` 仍包含未被跟注的部分，沒有「已套用」標記；日後（Phase 5）由呼叫端套用時須確保只套用一次。
   結算明細（各池金額、資格、得主）尚未公開到狀態、視圖或事件。
7. **未來相容性**：新的 `TexasPublic` 不變式使 P3-04 之前序列化的攤牌狀態無法載入（目前沒有持久化）；`ShownHand` 的牌是否等於私有底牌，由引擎保證，`check_consistency` 無法驗證。
8. 入庫的兩份獨立參考被加了 `# noqa` 與格式重排，語意相同（已用 15 萬手比對）但不再是代理原檔。
9. API 序列化無法驗證（尚無 API 或傳輸層）；`asdict(GameState)` 仍含私有資料。
10. 沿用前幾階段：燒牌、盲注、籌碼的正式值待確認；措辭偵測為啟發式；信任限制。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險：P3-00 已修補並通過複驗，是否正式標為已解決由人工決定。
- [ ] test-only Deck 與正式引擎的隔離：僅緩解，仍開放。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制：仍開放。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口：仍開放。

### 尚未驗收（P3-04 通過不代表已完成）

- Registry 登記與完整牌局契約驗證（P3-05）；P3-05 同時須處理結算的公開方式與套用機制。
- Room、GameSession、認證與授權、傳輸層、資料庫整合；PostgreSQL 測試（5 項 skipped，原因：未設定 `TEST_DATABASE_URL`，需要可丟棄的 PostgreSQL）。

---

## P3-04 七選五、攤牌亮牌、邊池結算與結果 — 已人工驗收（見上方結案決議）

日期：2026-11-16（Asia/Taipei）。依 P3-04 設計審查「照建議」實作（五項決策皆採建議）。
**未開始 P3-05**：未登記進 Registry，沒有 Room、GameSession、認證、傳輸層或資料庫；未 commit。
P3-03 的**行為**未改變；為實作亮牌與結算，確實修改了 P3-03 已結案的 `betting.py`、`engine.py`、`state.py` 與三個既有測試檔（範圍見下）。

### 採用的決策與已批准的規則契約

1. 契約批准（`settlement.py` 檔頭有完整文字）：① 未被跟注退回：唯一最大投入者取回「最大減第二大」（第二大含已棄牌與 all-in 座位），只做一次、在分池之前；
   ② 以不同的正數投入層級分層，有資格者＝未棄牌且投入達該層，棄牌籌碼計入金額但永不得池；③ **相鄰且資格相同的層先合併再分配**；
   ④ 每池在有資格者中比七選五，唯一有資格者直接得池；平手均分，餘數從「按鈕左側第一個座位」起順時針逐枚發給平手者，**按鈕座位最後**，每池各自計算；
   ⑤ 只剩一人：不比牌、不亮牌，得全部；⑥ 淨變動＝退回＋獲得－投入，總和為 0。
2. 攤牌亮牌：牌局以 `SHOWDOWN` 結束時，**所有未棄牌座位的底牌公開**（不可蓋牌），公開在 `TexasPublic.showdown`；只剩一人時不亮牌。
3. 名次：依 `points_delta` 由高到低的競賽排名（並列同名次，例如 1、1、3）。
4. 結算為純函式 `settle`／`settle_state`，**不改動狀態、不發新事件**；`calculate_result` 回傳各玩家的淨變動與名次（不是最終籌碼）。
5. 獨立性：派兩個獨立代理，**只憑文字**撰寫參考實作（結算參考、七張牌評估器）。
6. P3-04-0（只加測試）一併完成：多組盲注結構與「對手棄牌或 all-in 時不可加注」情境。

**契約範例更正**：設計審查稿的範例 5（兩個各 5 的相同資格層）無法由投入量建構。實際需要的是：兩位玩家各棄牌投入 3、三位玩家各投入 10 且其中兩位平手，
合併成 36 各得 18；若不合併，15 與 21 各自分餘數會變成 19 與 17。測試已改用此例。

### 新增與契約變更（須人工確認）

- `hands.best_of_seven(cards)`：恰好 7 張相異精確 `Card`，取 21 個五張組合的最大值（擴充已結案的 `hands.py`，`evaluate_five` 不變）。
- `settlement.py`：`Pot`、`Refund`、`Award`、`Settlement`（精確型別驗證與守恆檢查）、`build_pots`、`split_pot`、`odd_chip_order`、`settle`、`settle_state`。
  現實中不可能出現的輸入（已棄牌座位持有最大投入、無人有資格的層、無人留在局中）**一律拒絕**（fail closed）。
- `TexasPublic.showdown`（新增，預設空）與 `ShownHand`；不變式：`SHOWDOWN` 結束時必須恰好是所有未棄牌座位亮牌、牌彼此相異且不在公共牌上；其他情況必須為空。
- `betting.advance` 在河牌後或無人可下注而進入攤牌時建立 `showdown`；`TexasEngine.calculate_result` 實作（`not_implemented` 錯誤碼已移除）。
- 既有測試調整：`test_texas_engine.py`（結果測試改為實際結算、新增 `shown_cards` 豁免輔助）、`test_texas_raising.py`（契約套件改為 `results_supported=True` 並豁免已亮的牌）、
  `test_texas_setup.py`（欄位矩陣補 `showdown`、新增亮牌不變式測試）。
- 兩份獨立參考已納入測試目錄並註明來源：`settlement_reference_independent.py`、`seven_card_reference_independent.py`。

### 測試與獨立驗證

- `test_texas_settlement.py` 22 項：範例 1 到 5、按鈕座位最後拿餘數、單人無需比牌；**暴力 oracle**（逐籌碼層級掃描，與引擎的排序加差分寫法不同）、獨立代理的結算參考、引擎三方比對：
  2 到 3 座位、投入 0 到 6、所有棄牌與牌力並列組合，共超過 4 萬種全部一致；另 6000 組隨機（2 到 9 座位）一致；守恆、棄牌者不得獲池、有資格者才得池；
  經引擎發固定牌的端到端情境（單挑、平手與奇數籌碼、短額 all-in 只贏主池、未被跟注的退回、棄牌後不亮牌、名次並列）；
  **400 局隨機完整牌局**（含加注、邊池與平手）的 `calculate_result`，與「獨立七張評估器加獨立結算」逐一相符。
- `test_texas_seven.py` 31 項：19 個手算案例（皇家同花順、6 張同花順、輪牌、鐵支加三條、雙三條、三對的踢腳、不環繞等）、與獨立評估器的差分（隨機 3000 手、集中少數點數 2500 手、同花集中 1500 手）、輸入驗證、花色與順序無關。
- **精確窮舉（一次性，不在測試套件內）**：以獨立代理的列舉方法（點數多重集合乘上同花點數集合，組合數加權）涵蓋全部 133,784,560 手：
  代理的評估器與**引擎的 `best_of_seven`（190,346 個代表手牌，約 92 秒）**各自算出的九種牌型數量，全部與公認值完全相符
  （同花順 41,584 含皇家 4,324；鐵支 224,848；葫蘆 3,473,184；同花 4,047,644；順子 6,180,020；三條 6,461,620；兩對 31,433,400；一對 58,627,800；高牌 23,294,460），已記錄於證據檔 `manual_exact_seven_card_check`。
- `test_texas_blinds.py` 13 項（P3-04-0，只加測試）：盲注 1/2、3/7、25/50、100/250 下的最低下注、最低加注鏈、短額大盲、每街重置；以及 4 人桌情境（UTG 棄牌、小盲與大盲短籌碼 all-in，按鈕位只能跟注或棄牌）。
  P3-03 複驗中存活的兩個變異（盲注寫死為 10、把棄牌座位算成對手）現在都被抓到。
- 副本上 27 種變異（結算各環節、七選五、亮牌、名次、P3-03 的兩個缺口）：25 種直接被抓到；`state: showdown rule off` 最初存活，補測試後被抓到；
  另有 1 種（以錯誤座位底牌評估）補上正確的變異字串後被抓到。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P3-04 settlement：exit 0；22 passed in 9.90s
- P3-04 seven-card：exit 0；31 passed in 3.27s
- P3-04-0 blinds：exit 0；13 passed in 0.32s
- P3-03 texas raising：exit 0；19 passed in 1.30s
- P3-02 texas engine：exit 0；30 passed in 5.73s
- P3-01 texas setup：exit 0；60 passed in 0.45s
- P3-00 extensions：exit 0；21 passed in 0.12s
- P3-00 deck failure and isolation：exit 0；7 passed in 0.97s
- P2-F projection：exit 0；15 passed in 0.12s
- P2-F contract suite：exit 0；31 passed in 1.43s
- P2-E texas hands：exit 0；55 passed in 3.10s
- P2-D registry：exit 0；34 passed in 0.15s
- P2-C engine contract：exit 0；28 passed in 0.15s
- R2 public field matrix：exit 0；25 passed in 0.11s
- R1 public isolation：exit 0；19 passed in 0.13s
- Original P2-B regression：exit 0；124 passed in 1.95s
- P2-A regression：exit 0；127 passed in 0.21s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.84s
- Mypy：exit 0；Success: no issues found in 52 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；59 files already formatted
- Full backend suite：exit 0；665 passed, 5 skipped, 1 warning in 28.70s
- pip check：exit 0；No broken requirements found.

完整 backend **665 passed、5 skipped**（598＋67；連跑 3 次穩定；5 項 PostgreSQL 測試仍未驗證通過）。證據檔 `P3_04_TEST_EVIDENCE.json`；
`settlement.py` SHA-256 `ec0fda0a3ea5a32ef20aa1bbe643af24cb85299871c4d8b657ab11fd9a99dfb6`；`hands.py` `8aa61ca3db938fb1401f8ed9b06c2bf35ede32dd70fb289253c1b6f9fef87c14`；`betting.py` `6dc56d39779327f247b09a8c74c17025af7bcee69189f253e3bc59931a750d4f`；`test_texas_settlement.py` `9293824bf6b27467a676b2367decd7b792feb785e1f036e0bbd6b2d722fcae94`。
B／R1／R2／C／D／E／F／P3-00／P3-01／P3-02／P3-03 證據未覆寫。

### 尚未解決的限制

- 這些契約選擇（合併規則、退回定義、餘數順序、按鈕最後、亮牌全部未棄牌座位、競賽名次）雖經「照建議」批准，仍須在獨立複驗中檢視；獨立代理只驗證「實作符合契約文字」，不驗證「契約文字就是正確的德州規則」。
- 結算明細（各池金額、資格與獲得者）只在 `settle_state` 的回傳值中，**尚未公開到 `TexasPublic`、視圖或事件**；前端需要時再決定公開方式。`calculate_result` 只回傳淨變動與名次。
- `best_of_seven` 每次約 1 毫秒（21 次五張評估），攤牌結算每席約 1 毫秒，目前可接受，未做效能優化。
- 現實中不可能的結算輸入採 fail-closed 拒絕，獨立結算參考對這類輸入的行為不同，測試只餵可達輸入。
- 未被跟注的部分現在會在結算退回，但 P3-03 的下注階段仍把它留在底池（狀態中的 `pot` 不扣退回），兩者的一致性由結算函式保證。
- 燒牌、盲注、籌碼的正式值仍待確認；措辭偵測仍為啟發式；P2-A 風險 2、3、4 與 PostgreSQL 5 項測試仍開放。
- Registry 登記（P3-05）、Room、GameSession、認證、傳輸層、資料庫整合未實作。P3-04 是否結案須人工獨立驗收。

---

## P3-03 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P3-03 = **CONDITIONAL PASS**，核准 **P3-03 階段**（無限注下注規則：bet、raise、all-in、最小加注、重新開放，以及建局時一輪無須行動的統一處理）結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P3-04，未做任何 Git 寫入。
注意：P3-03 的實作與文件尚未提交。

### 驗收範圍與獨立複驗結果

- 範圍：`texas_holdem/betting.py`、`engine.py`、`events.py`、`state.py`、`hand.py` 的變更與 `test_texas_raising.py`、既有測試的調整。
- 獨立複驗：核心、`hands.py`、`positions.py`、`rules.py`、migration 與 P3-02 證據相對 HEAD 無差異；P3-03 證據 39 個來源雜湊、九份舊證據雜湊與 20 項檢查退出碼皆吻合。
- Backend：**598 passed、5 skipped**（重跑 4 次穩定）；5 項 PostgreSQL 測試**尚未驗證通過**。Mypy、Ruff、格式檢查通過。
- 獨立參考模擬器（待回應佇列加「面對的下注成長量」，與引擎的已行動旗標加 `bet_seen` 寫法不同）逐步比對：
  8000 局隨機對局、47,265 次決策，合法動作種類、最小與最大金額、跟注額、輪到的座位、籌碼、本街投入額、目前下注、最低增量，以及結束時的公共牌、結束方式、籌碼與投入額全部一致；
  24,540 次非法金額嘗試皆被拒絕且狀態不變；盲注結構 1/2、25/50、3/7 各 2500 局亦全部一致。
- 作者的 27 種變異**未逐一重跑**：獨立抽驗 6 種，3 種被抓到、1 種為等價變異（我設計不佳）、2 種揭露下述覆蓋缺口。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件

1. **專案測試覆蓋缺口（建議補強）**：
   - 所有專案測試只用 5/10 盲注，「翻牌前最低加注的基準寫死為 10」的變異未被抓到；引擎本身正確，但日後回歸不會被發現。需補不同盲注結構的測試。
   - 「判斷對手能否行動時把已棄牌座位算進去」的變異未被抓到；需補情境測試：4 人桌，UTG 棄牌，小盲與大盲短籌碼 all-in，按鈕位只能跟注或棄牌。
2. **獨立性有限**：參考模擬器寫法不同，但規則選擇與引擎出自同一份理解（累計式重新開放、對手全 all-in 或棄牌時不可下注或加注、大盲不足額的最低加注基準、「加到」金額）。這些仍是待人工確認的決策，不是規格內容。
3. **未被跟注的部分**：下注或加注超過任何人跟注的額度時，多出的部分目前留在底池，須在 P3-04 結算時退回。
4. 燒牌、盲注、籌碼的正式值與標準德州預設仍待人工確認；建局時一輪無須行動即發完各街（事件不回傳、燒掉的牌不保留）。
5. 契約套件的措辭偵測仍為啟發式；擴充註冊不檢查 `__post_init__` 內容品質；擴充白名單為全域。
6. 沿用前幾階段的信任限制。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險：P3-00 已修補並通過複驗，是否正式標為已解決由人工決定。
- [ ] test-only Deck 與正式引擎的隔離：僅緩解，仍開放。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制：仍開放。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口：仍開放。

### 尚未驗收（P3-03 通過不代表已完成）

- 七選五、邊池、結算、未被跟注部分的退回、攤牌亮牌與蓋牌（P3-04）。
- Registry 登記與含結果的完整契約（P3-05）。
- Room、GameSession、認證與授權、傳輸層、資料庫整合；PostgreSQL 測試（5 項 skipped）。

---

## P3-03 德州無限注下注規則（bet、raise、all-in、最小加注、重新開放） — 已人工驗收（見上方結案決議）

日期：2026-11-16（Asia/Taipei）。依 P3-03 規劃 7 項決策（照建議）實作。
**未開始 P3-04**：沒有七選五、邊池、結算、攤牌亮牌與未被跟注部分的退回；`TexasEngine` 未登記進 Registry；未 commit。

### 採用的決策

1. `bet`、`raise` 的 `amount` 為「加到」：該玩家本街投入的**總額**。
2. 最低下注＝大盲；最低加注增量＝上一次完整加注的大小（至少大盲），每街重置為大盲。
3. 重新開放規則（累計式）：每個座位記下上次行動時面對的最高下注（`bet_seen`）；只有當下注自那時起增加至少一個最低增量，該座位才能再加注。
   單一短額 all-in 不重新開放；多個短額 all-in 累計達到一個完整加注則會重新開放。
4. 大盲不足額時，翻牌前最低加注到 max(目前下注, 大盲) 加上最低增量。
5. 批准統一建局行為：建局後若這一輪已無須行動（例如唯一可行動的座位無須回應），直接發完剩餘各街（處理 P3-02 保留條件 1）。
6. `ActionTaken` 新增 `total`（本街總額，必填）。
7. 燒牌、盲注、籌碼的正式值仍待確認（P3-03 不依賴，測試仍用暫定值）。

### 規則細節（實作時的明確選擇）

- `all_in`：總額不超過跟注額＝不足額跟注（同跟注）；超過＝加注。增量不小於最低增量為完整加注並更新最低增量，否則為短額加注，不更新。
- 下注或加注到恰好等於全部籌碼，視為 all-in。
- **對手全部 all-in 或棄牌時，該座位不能下注或加注**（無人可對抗），只能跟注或棄牌；此為本次的明確選擇，規格未定義。
- 能過牌時可棄牌；翻牌前大盲保有選擇權，可過牌或加注。
- 新增錯誤碼 `bad_amount`（金額超出允許範圍）；`bad_payload` 用於缺少或多餘的金額；`not_supported_yet` 已移除。

### 契約與狀態變更

- `SeatState.bet_seen`；`TexasPublic.min_raise`（建局時為大盲）並新增不變式：`min_raise ≥ 1`、任一座位的 `bet_seen` 不得高於 `current_bet`。
- `LegalActions` 新增 `min_to`、`max_to`（bet／raise 的合法範圍，含邊界）。
- `betting.advance` 與 `legal_actions` 的簽章調整；`create_game` 在創建時判斷一輪是否已完成。
- 既有測試調整：`test_texas_engine.py`（原「尚未支援」期望改為新規則、事件加 `total`、隨機對局加入下注與加注）、`test_texas_setup.py`（欄位矩陣補新欄位）。

### 新增與測試

- `test_texas_raising.py` 19 項（手算情境）：單挑下注、加注與短額 all-in 鏈；金額邊界含上下限；加到全部籌碼；翻牌前再加注鏈的最低增量更新；大盲不足額；短額 all-in 下注不改最低增量；
  對手全 all-in 不可加注；經典情境（下注 100、加到 300、短額 all-in 到 350：加注者不能再加注、原下注者可以）；完整加注後重新開放；多個短額 all-in 累計重新開放（4 人桌）；大盲選擇權與過牌加注；每街重置；
  所有非法金額與 payload 皆拒絕且不改狀態；建局時無須行動的局面直接發完；契約套件在含下注與加注的腳本下通過。
- 隨機對局（1500 局）現在包含 bet、raise（超過 500 次）：每步積分守恆、牌不重複、街內下注與最低增量不遞減、輪到者可行動、決定性、必定結束。
- 副本上 27 種變異：24 種被抓到；`total>=needed -> >` 與 `bet_seen invariant off` 最初存活，補測試後被抓到；
  `bet_seen not set on check` 為在可達狀態下的等價變異（過牌時面對的下注之後無人能再加注）。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P3-03 texas raising：exit 0；19 passed in 1.33s
- P3-02 texas engine：exit 0；30 passed in 5.57s
- P3-01 texas setup：exit 0；59 passed in 0.46s
- P3-00 extensions：exit 0；21 passed in 0.12s
- P3-00 deck failure and isolation：exit 0；7 passed in 0.89s
- P2-F projection：exit 0；15 passed in 0.12s
- P2-F contract suite：exit 0；31 passed in 0.85s
- P2-E texas hands：exit 0；55 passed in 3.18s
- P2-D registry：exit 0；34 passed in 0.15s
- P2-C engine contract：exit 0；28 passed in 0.16s
- R2 public field matrix：exit 0；25 passed in 0.11s
- R1 public isolation：exit 0；19 passed in 0.11s
- Original P2-B regression：exit 0；124 passed in 2.06s
- P2-A regression：exit 0；127 passed in 0.21s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.89s
- Mypy：exit 0；Success: no issues found in 46 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；53 files already formatted
- Full backend suite：exit 0；598 passed, 5 skipped, 1 warning in 15.64s
- pip check：exit 0；No broken requirements found.

完整 backend **598 passed、5 skipped**（578＋20；連跑 3 次穩定；5 項 PostgreSQL 測試仍未驗證通過）。證據檔 `P3_03_TEST_EVIDENCE.json`；
`betting.py` SHA-256 `869a0bb7e383a207994d46c39d7a8193ab3e3345f64304b440b506176e12c5db`；`engine.py` `c9f29f764b0a5542d87d654afa97bf4a17c2065ac7813d60df3e992238b73a69`；`state.py` `5b63687e181cacc2e3b8eaef8085975ffae50182c70a7c0e2cd8e705da13222b`；`test_texas_raising.py` `3173553534d336c2dc977d67a7e0d90d37422a03c57b98b4a3b4a17543b9a452`。
B／R1／R2／C／D／E／F／P3-00／P3-01／P3-02 證據未覆寫。

### 尚未解決的限制

- 七選五、邊池、結算、未被跟注部分的退回、攤牌亮牌與蓋牌（P3-04）；Registry 登記與含結果的完整契約（P3-05）。
- 累計式重新開放、「對手全 all-in 不可加注」、大盲不足額的最低加注等為明確選擇而非規格內容，仍待人工確認；燒牌、盲注、籌碼的正式值亦待確認。
- 獨立參考模擬器尚未針對加注規則重做（待獨立複驗）；`bet_seen` 的過牌記錄在可達狀態下無可觀察效果。
- 契約套件的措辭偵測仍為啟發式；P2-A 風險 2、3、4 與 PostgreSQL 5 項測試仍開放；Room、GameSession、認證、傳輸與資料庫整合未實作。P3-03 是否結案須人工獨立驗收。

---

## P3-02 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P3-02 = **CONDITIONAL PASS**，核准 **P3-02 階段**（棄牌、過牌、跟注、不足額 all-in 的街狀態機與引擎，含 P3-02-0 核心擴充一致性檢查）結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P3-03，未做任何 Git 寫入。
注意：P3-02 的實作與文件尚未提交。

### 驗收範圍與獨立複驗結果

- 範圍：`texas_holdem/betting.py`、`events.py`、`engine.py`、`state.py` 的擴充，`core` 的 `check_consistency` 契約，以及相關測試與契約套件的 `results_supported`。
- 獨立複驗：核心 Card、Deck、`engine*.py`、`projection.py`、`registry.py`、`hands.py`、`positions.py`、`rules.py`、migration 與 P3-01 證據相對 HEAD 無差異；
  P3-02 證據 38 個來源雜湊、八份舊證據雜湊與 19 項檢查退出碼皆吻合。
- Backend：**578 passed、5 skipped**（重跑 4 次穩定）；5 項 PostgreSQL 測試**尚未驗證通過**。Mypy、Ruff、格式檢查通過。
- 獨立參考模擬器（佇列式寫法）與引擎逐步比對 6000 局隨機對局（含短籌碼、燒牌開關），在建局差異處理後全部一致（輪到的座位、公共牌、籌碼、投入額、棄牌、結束方式、底池）。
- 對抗輸入（大小寫或空白的動作名稱、`GameAction` 與 payload 子類別、非德州狀態、局外玩家）皆被正確拒絕；靜態守衛能抓違規呼叫 `create_game_for_testing`。
- 作者的 37 種變異**未逐一重跑**：獨立抽驗 6 種，5 種被抓到，1 種為等價變異。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件

1. **建局不一致（建議 P3-03 前統一）**：建局時若唯一可行動的座位無須回應任何東西（例如大盲 all-in 少於小盲），引擎仍要求它「過牌」；同樣局面出現在中途時 `advance` 會直接跳過並發完各街。
   位置：`hand.py` 第一位行動者選取與 `engine.py` 的 `_normalise`。隨機樣本約 4.9%（294／6000）出現多餘動作與事件；不影響積分與牌。
2. 驗證的獨立性有限：作者的隨機對局以引擎自己的合法動作清單選動作；獨立性來自本次的參考模擬器，未納入專案測試。
3. 正式規則值與標準解讀仍待人工確認：燒牌（暫定 False）、盲注、籌碼、大盲選擇權、翻牌後先行者。
4. 創建時無人可行動：直接發完剩餘各街並回傳已結束的基準狀態，事件不回傳（`event_seq` 已前進）；燒掉的牌不保留在狀態中。
5. 契約套件的措辭偵測仍為啟發式；擴充註冊不檢查 `__post_init__` 內容品質；擴充白名單為全域。
6. 契約變更（`check_consistency`、`SeatState` 與 `TexasPublic` 新欄位與不變式、五個既有測試檔的調整）已於 P3-02 章節記錄並經獨立複驗。
7. 沿用前幾階段的信任限制。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險：P3-00 已修補並通過複驗，是否正式標為已解決由人工決定。
- [ ] test-only Deck 與正式引擎的隔離：僅緩解，仍開放。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制：仍開放。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口：仍開放。

### 尚未驗收（P3-02 通過不代表已完成）

- bet、raise、超額 all-in、最小加注、短額 all-in 重新開放規則（P3-03）。
- 七選五、邊池、結算、攤牌亮牌與蓋牌（P3-04）；Registry 登記與含結果的完整契約（P3-05）。
- Room、GameSession、認證與授權、傳輸層、資料庫整合；PostgreSQL 測試（5 項 skipped）。

---

## P3-02 德州各街狀態機與棄牌／過牌／跟注引擎（含 P3-02-0 前置） — 已人工驗收（見上方結案決議）

日期：2026-11-16（Asia/Taipei）。依 P3-02 規劃 8 項決策（照建議）實作。
**未開始 P3-03**：沒有 bet、raise、超額 all-in、最小加注與重新開放規則；沒有邊池、七選五、結算、攤牌亮牌；`TexasEngine` 未登記進 Registry；未 commit。
本輪**有意修改已結案的核心契約**（見下方「契約變更」）。

### 採用的決策

1. 切分方案 A：P3-02 做棄牌、過牌、跟注與不足額 all-in（行為同跟注）；`bet`、`raise` 與超過跟注額的 all-in 一律回傳 `not_supported_yet`，留給 P3-03。
2. 批准修改核心：已註冊的公開擴充類別必須實作 `check_consistency`，由 `GameState`／`PlayerView` 建構時呼叫（投影時也會重跑）。
3. 燒牌：`TexasRules.burn_cards`，暫定 False，**正式值待人工確認**；測試涵蓋開與關。
4. 翻牌前大盲保有選擇權（本階段只能過牌）。
5. 翻牌後先行者：按鈕左側第一個可行動者（單挑為大盲）；自動跳過棄牌與 all-in 座位。
6. 事件序號存於 `TexasPublic.event_seq`（下一個事件使用的序號）。
7. 牌局結束：只剩一人→`LAST_STANDING`；河牌後或無人可下注→發完剩餘各街，`SHOWDOWN`；`GameStatus.FINISHED`，**底池尚未分配**，`calculate_result` 回傳 `not_implemented`。攤牌亮牌與蓋牌規則仍未定義，留給 P3-04。
8. 能過牌時允許棄牌。

### 契約變更（須人工確認）

- `PublicExtension` 新增必須覆寫的 `check_consistency(public)`；註冊時缺少會被拒；`GameState`／`PlayerView` 在建構時呼叫。
- `SeatState` 新增 `street_committed`、`acted`；`all_in` 現在等價於「籌碼為 0」。`TexasPublic` 新增 `ended`、`event_seq`，並強制：`current_bet` 等於本街最高投入、公共牌張數與街別相符、剩一個未棄牌座位必須已結束。
- `TexasPublic.check_consistency`：座位名單須等於 `public.players`、每座位 `stack + committed == Player.points`、`FINISHED` 與結束狀態一致、輪到的座位必須能行動。
  這處理了 P3-01 保留條件 1（狀態不變式缺口）。
- 為相容既有測試所做的修改：`test_extensions.py`（`TablePot` 加 `check_consistency`、新增註冊拒絕案例）、`test_engine_contract_suite.py`（`TableNote` 加 `check_consistency`）、
  `test_texas_setup.py`（輔助函式與欄位矩陣補新欄位，並新增 payload 的欄位矩陣；強制測試涵蓋事件 payload）、
  `test_deck_failure_and_isolation.py`（靜態守衛允許引擎內部對 `start_hand_for_testing` 的包裝，其他任何使用，含 `create_game_for_testing`，仍視為違規）。

### 新增內容

- `texas_holdem/betting.py`（合法動作、各街推進純函式）、`events.py`（已註冊的公開事件 payload：`ActionTaken`、`StreetDealt`、`HandEnded`）、`engine.py`（`TexasEngine`、`TexasPayload`；固定牌序只能經 `create_game_for_testing`）。
- 契約套件新增 `results_supported` 場景欄位（尚無結算時，結束後須回安全的 `GameError`）。
- 測試 `test_texas_engine.py` 30 項：手寫合法動作表、各種拒絕碼且不改狀態、固定牌序的完整流程（單挑過牌到攤牌含事件、燒牌開關、三人跟注與大盲選擇權、全員棄牌、翻牌後棄牌、不足額 all-in、全員 all-in 發完剩餘各街、創建時無人可行動、只剩一位可行動者）、
  事件序號連續、視圖不含底牌與牌堆、共用契約套件通過、1500 局隨機對局（每步檢查積分守恆、牌不重複、公共牌張數、版本與序號、輪到者可行動、決定性、必定結束，且兩種結束方式與 all-in 路徑皆被走到）、300 局隨機拒絕不改狀態。
- 副本上 37 種變異：35 種被抓到；`game over unchecked` 為等價變異（結束狀態的 `turn` 必為 None）；
  `live-seat rule off` 最初存活，已補測試後被抓到。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P3-02 texas engine：exit 0；30 passed in 7.14s
- P3-01 texas setup：exit 0；58 passed in 0.39s
- P3-00 extensions：exit 0；21 passed in 0.10s
- P3-00 deck failure and isolation：exit 0；7 passed in 0.68s
- P2-F projection：exit 0；15 passed in 0.13s
- P2-F contract suite：exit 0；31 passed in 0.73s
- P2-E texas hands：exit 0；55 passed in 2.62s
- P2-D registry：exit 0；34 passed in 0.12s
- P2-C engine contract：exit 0；28 passed in 0.14s
- R2 public field matrix：exit 0；25 passed in 0.08s
- R1 public isolation：exit 0；19 passed in 0.09s
- Original P2-B regression：exit 0；124 passed in 1.78s
- P2-A regression：exit 0；127 passed in 0.20s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.72s
- Mypy：exit 0；Success: no issues found in 45 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；52 files already formatted
- Full backend suite：exit 0；578 passed, 5 skipped, 1 warning in 14.84s
- pip check：exit 0；No broken requirements found.

完整 backend **578 passed、5 skipped**（542＋36；連跑 6 次穩定；5 項 PostgreSQL 測試仍未驗證通過）。證據檔 `P3_02_TEST_EVIDENCE.json`；
`betting.py` SHA-256 `c1891abd0f2010b6b6d8bab05cfa5c54a7485c82494d8e661e9646e8332f9fa9`；`engine.py` `c1432d74de9c0f98e099e491a73ec8da3f0823227d0f7de573f6c0212657f289`；`state.py` `cfaac8ec06ac3efd0dd34fd81e6ca3fe6926b741ee8d70b7f360a108d7ea5620`；`test_texas_engine.py` `289db665a577250f1ffeaf98f744fe48451f95d50e3f64ea9490758c991d4556`。
B／R1／R2／C／D／E／F／P3-00／P3-01 證據未覆寫。

### 尚未解決的限制

- bet、raise、超額 all-in 與最小加注、短額 all-in 重新開放規則（P3-03）；七選五、邊池、結算、攤牌亮牌與蓋牌（P3-04）；Registry 登記與完整契約（含結果）（P3-05）。
- 燒牌、盲注、籌碼的正式值與標準德州預設仍待人工確認；一街結束的判定採標準規則，大盲選擇權亦為標準解讀。
- 若創建時無人可行動，`create_game` 直接發完剩餘各街並回傳已結束的基準狀態（事件未回傳，`event_seq` 已前進）。
- 燒掉的牌不保留在狀態中（重播依賴受保護的初始牌序）；契約套件的措辭偵測仍為啟發式。
- 單手牌範圍；P2-A 風險 2、3、4 與 PostgreSQL 5 項測試仍開放；Room、GameSession、認證、傳輸與資料庫整合未實作。P3-02 是否結案須人工獨立驗收。

---

## P3-01 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P3-01 = **CONDITIONAL PASS**，核准 **P3-01 建局階段**（含 P3-01-0 前置）結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P3-02，未做任何 Git 寫入。
注意：P3-01 的實作與文件尚未提交。

### 驗收範圍與獨立複驗結果

- 範圍：`texas_holdem/` 的 `rules.py`、`positions.py`、`state.py`、`hand.py`，`core/validation.py`，契約套件的洩漏偵測擴充與擴充欄位矩陣強制。
- 獨立複驗：`models.py`、`engine*.py`、`projection.py`、`registry.py`、Card、`hands.py`、migration、P3-00 證據相對 HEAD 無差異；
  P3-01 證據 34 個來源雜湊、七份舊證據雜湊與 18 項檢查退出碼皆吻合。
- Backend：**542 passed、5 skipped**（連跑 6 次穩定）；5 項 PostgreSQL 測試**尚未驗證通過**。Mypy、Ruff、格式檢查通過。
- 獨立 oracle：自寫的位置參考實作對 12 個座位號中所有 2 到 9 人座位組合與每個按鈕共 23,760 種，0 項不一致；
  4000 次隨機 `start_hand`（含短籌碼邊界）逐項比對籌碼、盲注、全下旗標、底池、底牌與發牌順序、剩餘牌、先行者與積分守恆，0 項不一致。
- 對抗輸入：`Player`／`Deck` 子類別、布林按鈕、同一玩家佔兩座位、牌數不足牌組皆被拒絕。
- 作者的 28 種變異結果**未經獨立重跑**，只核對了數量與文件一致。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件

1. **狀態不變式缺口（P3-02 動手前須處理）**：以下實測被接受——`GameState` 接受座位名單與 `public.players` 不一致的 `TexasPublic`；
   擴充資料的籌碼可與 `Player.points` 完全不符；`current_bet` 可大於任何投入額；籌碼為 0 但未標 all-in 的 `SeatState`。
   目前只有 `start_hand` 產生有效狀態；P3-02 的動作會改寫這些欄位，須先在建構時強制一致性。
2. **措辭偵測為啟發式**：`2 c`、`2-c`、`10 h`、`K D`、`ace ♠`、零寬字元、`rank=2 suit=C` 偵測不到；全大寫訊息中的 `AS` 會誤判。通過偵測不代表沒有洩漏。
3. **正式規則值與決策仍待人工確認**：盲注金額、籌碼為測試 fixture（小盲 5、大盲 10、籌碼 100），燒牌暫定 False，發牌順序與初始按鈕規則；
   標準德州預設（短額 all-in 不重新開放加注、加注為「加到」）仍待確認。
4. 擴充註冊不檢查 `__post_init__` 內容品質（由欄位矩陣測試把關）；擴充白名單為全域；契約套件仍只在 stub 上完整驗證，`start_hand` 尚非引擎。
5. 單手牌範圍；死按鈕、出局玩家與跨手輪替僅有純函式 `next_button`，無狀態化；建局不產生事件（初始狀態為事件序號 0 的基準快照）。
6. 沿用前幾階段的信任限制。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險：P3-00 已修補並通過複驗，是否正式標為已解決由人工決定。
- [ ] test-only Deck 與正式引擎的隔離：僅緩解，仍開放。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制：仍開放。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口：仍開放。

### 尚未驗收（P3-01 通過不代表已完成）

- 玩家動作、各街推進、下注規則、七選五、邊池、結算（P3-02～P3-04）；完整引擎、Registry 登記與牌局測試（P3-05）。
- Room、GameSession、認證與授權、傳輸層、資料庫整合；PostgreSQL 測試（5 項 skipped）。

---

## P3-01 德州建局、盲注與按鈕（含 P3-01-0 前置） — 已人工驗收（見上方結案決議）

日期：2026-11-15（Asia/Taipei）。依 P3-01 規劃 8 項決策（照建議）實作。
**未開始 P3-02**：沒有任何玩家動作、各街推進、下注、邊池、結算、`GameEngine` 實作或 Registry 登記；未 commit。
本輪**有意修改**已結案的 `deck.py`、`extensions.py`、契約套件與其測試（範圍見下）。

### 採用的決策與待確認項目

1. 規則值由呼叫端提供，產品程式**不含預設盲注或籌碼**；測試使用標為 fixture 的暫定值（小盲 5、大盲 10、籌碼 100），**不是產品設定，待人工提供正式值**。
2. 是否燒牌：`TexasRules.burn_cards` 為必填欄位，P3-01 不使用（燒牌發生在翻牌前，P3-02 才生效）；暫定值 False，**待人工確認**。
3. 初始按鈕為最小座位號，之後以 `next_button` 依座位號遞增輪替（座位可有空號）。
4. 座位號遞增即順時針。
5. 發牌順序（隨規則版本記錄）：從小盲座位開始順時針每人一張、共兩輪；單挑時小盲即按鈕。
6. `Player.points` 視為本局開始時的桌上籌碼；零籌碼玩家回傳 `zero_stack`；活動籌碼放在 `SeatState.stack`。
7. 籌碼不足盲注時，投入全部並標為 all-in；第一位行動者為名義座位或其後第一個仍可行動的座位，無人可行動時 `turn` 為 None。
8. 建局不產生事件；初始狀態視為事件序號 0 的基準快照（未改 `create_game` 契約）。

### P3-01-0：P3-00 保留條件處理結果（待複驗）

- **條件 1（擴充資料洩漏）**：契約套件現在對視圖的擴充資料、公開事件 payload 做隱藏牌比對；新增 `revealed` 場景欄位，讓引擎在攤牌等時點合法公開的牌可被豁免。
- **條件 2（措辭變體）**：新增 `reveals_card`，偵測牌面碼（任意大小寫）、`repr`、牌名（如 two of clubs）、點數加花色符號；單獨的點數或花色不算。
  已知盲點：小寫 `as`／`ad`／`ah`／`ac` 是一般英文單字，不視為牌面碼（僅大寫形式被偵測），否則會因隨機發牌造成不穩定的誤判。
- **條件 3（擴充欄位驗證）**：新增 `core/validation.py` 公開的共用精確型別驗證函式；擴充機制新增 `registered_public_extensions()`／`registered_event_payloads()`；
  測試輔助 `extension_matrix.py` 要求每個 `app/` 下註冊的擴充類別都有欄位矩陣，缺少時測試失敗（`TexasPublic`、`SeatState` 已有）。
  註冊本身仍不檢查 `__post_init__` 的內容品質，品質由欄位矩陣測試把關。
- **條件 5 的一部分**：失敗的 Deck 的 `repr` 現在標示 `unavailable=True`。

### 新增內容

- `core/validation.py`、`texas_holdem/rules.py`（`TexasRules`）、`positions.py`（座位、按鈕、盲注位置純函式）、`state.py`（`Street`、`SeatState`、註冊的 `TexasPublic`）、
  `hand.py`（`start_hand`：經 `require_production_deck`；`start_hand_for_testing`：僅供受信任測試，不匯出，靜態守衛確保應用程式碼不使用）。
- 測試：`test_texas_setup.py` 54 項（手寫位置表 16 列、2 到 9 人逐一建局、發牌順序、短籌碼、拒絕案例、欄位矩陣、投影不洩漏、模組無框架匯入），
  契約套件 +8（6 種新洩漏引擎、無害擴充與豁免、措辭偵測）。
- 副本上 28 種變異（位置、盲注、發牌、閘門、狀態不變式、規則、共用驗證）全被抓到；其中「重複座位」最初存活，已補測試後被抓到。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P3-01 texas setup：exit 0；54 passed in 0.40s
- P3-00 extensions：exit 0；19 passed in 0.11s
- P3-00 deck failure and isolation：exit 0；7 passed in 0.15s
- P2-F projection：exit 0；15 passed in 0.13s
- P2-F contract suite：exit 0；31 passed in 0.83s
- P2-E texas hands：exit 0；55 passed in 3.24s
- P2-D registry：exit 0；34 passed in 0.15s
- P2-C engine contract：exit 0；28 passed in 0.16s
- R2 public field matrix：exit 0；25 passed in 0.11s
- R1 public isolation：exit 0；19 passed in 0.12s
- Original P2-B regression：exit 0；124 passed in 2.27s
- P2-A regression：exit 0；127 passed in 0.21s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.93s
- Mypy：exit 0；Success: no issues found in 41 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；48 files already formatted
- Full backend suite：exit 0；542 passed, 5 skipped, 1 warning in 8.47s
- pip check：exit 0；No broken requirements found.

完整 backend **542 passed、5 skipped**（480＋62；5 項 PostgreSQL 測試仍未驗證通過）。證據檔 `P3_01_TEST_EVIDENCE.json`；
`hand.py` SHA-256 `60642679f88bcb8b7af6dff38f1bd2fdbb20a32b0a33aab7c7606c2ac351c476`；`positions.py` `40588854608daf47328105269ff3a92a5ccfd38cd22b718706946f90b36a573f`；`state.py` `f7d41b87fcc54cba769f35fdc24c06307ba570d30f6071ecfe1eb06258856264`；`validation.py` `47faf17e0c39fd15942d7ddadf82b71728053ea2b46a3be0cb90c1c3d23cfe2d`；
`test_texas_setup.py` `0a685b9e5f5e128d9751afd8887d832c309968b1acf9894160f6c90587463b02`。B／R1／R2／C／D／E／F／P3-00 證據未覆寫。

### 尚未解決的限制

- 盲注金額、籌碼、燒牌的正式值與標準德州預設（短額 all-in 不重新開放加注、加注為「加到」）仍待人工確認；發牌順序與初始按鈕規則一旦確認即寫入規則版本。
- 擴充白名單仍為全域；註冊不檢查 `__post_init__` 內容；契約套件仍只在 stub 上完整驗證（`start_hand` 尚非引擎）。
- 單手牌範圍；死按鈕、出局玩家與跨手輪替僅有純函式 `next_button`，無狀態化。
- P2-A 風險 2、3、4 與 PostgreSQL 5 項測試仍開放；Room、GameSession、認證、傳輸與資料庫整合未實作。P3-01 是否結案須人工獨立驗收。

---

## P3-00 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P3-00 = **CONDITIONAL PASS**，核准 **P3-00 前置加固階段**結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P3-01，未做任何 Git 寫入。
注意：工作區仍有尚未提交的 Phase 2 收尾文件與 P3-00 實作。

### 驗收範圍與獨立複驗結果

- 範圍：Deck 失敗關閉、test-only 靜態守衛、契約套件補缺口、`HandRank` 語意驗證、公開資料／事件 payload 擴充機制。
- 獨立複驗：`card.py`、`registry.py`、migration、舊測試與七份舊證據無差異；P3-00 證據 27 個來源雜湊、六份舊證據雜湊與 17 項檢查退出碼皆吻合。
- Backend：**480 passed、5 skipped**；5 項 PostgreSQL 測試**尚未驗證通過**。Mypy、Ruff、格式檢查通過。
- 對抗驗證：失敗的 Deck 經 `copy`／`deepcopy`／pickle 重建後仍不可用；可達強度集合與 `HandRank` 接受集合完全相等（7462）；
  建構後被換成未註冊類別的擴充資料在投影時被拒；靜態守衛能抓直接使用。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件（前三項須在 P3-01 實作德州擴充資料前處理）

1. **契約套件抓不到經由擴充資料洩漏的隱藏牌**：視圖只檢查 `repr(card)`；把牌面碼放進公開擴充資料字串、
   送到每個玩家視圖的引擎未被偵測。須對擴充資料與事件 payload 的文字做牌面碼比對。
2. **錯誤訊息洩漏的格式變體抓不到**：小寫牌面碼（如 `2c`）、牌名（如 `Two of Clubs`）通過套件。
3. **擴充機制不強制欄位驗證**：註冊只要求有 `__post_init__`，內容為 `pass` 也可通過；實測未驗證的註冊擴充可接受帶隱藏屬性的 `str` 子類別，
   投影後仍保留。須為每個擴充類別要求欄位矩陣測試，並公開共用的精確型別驗證函式。
4. **P2-A 風險 2 的靜態守衛可被繞過**（如 `getattr(Deck, "for_" + "testing")`）：僅防誤用，風險 2 仍開放。
5. 失敗的 Deck 的 `repr` 仍顯示 `remaining_count=52`；擴充白名單為全域，測試中會累積註冊。
6. 沿用前幾階段的信任限制；契約套件仍只在 stub 上驗證。
7. 標準德州預設（短額 all-in 不重新開放加注、加注為「加到」）與單手牌範圍仍待人工確認；盲注金額、初始積分、是否燒牌**尚未提供**。

### P2-A 持續開放事項（狀態更新）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險：P3-00 已實作失敗關閉並通過獨立複驗，**修補成立**；
  仍保留未勾選，是否正式標記為已解決由人工決定。
- [ ] test-only Deck 與正式引擎的隔離：僅緩解（見條件 4），仍開放。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制：仍開放。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口：仍開放。

### 尚未驗收（P3-00 通過不代表已完成）

- 德州專屬公開資料、事件 payload、盲注、按鈕、各街、下注、七選五、邊池、結算與引擎（P3-01～P3-05）。
- Room、GameSession、認證與授權、傳輸層、資料庫整合；PostgreSQL 測試（5 項 skipped）。

---

## P3-00 Phase 3 前置加固 — 已人工驗收（見上方結案決議）

日期：2026-11-15（Asia/Taipei）。依 Phase 3 規劃 5 項決策（照建議）實作。
**未開始 P3-01**：沒有任何德州狀態、盲注、下注、邊池或引擎；未接 Registry；未 commit。
本輪**有意修改**先前已結案的檔案（`deck.py`、`models.py`、`engine_types.py`、`engine.py`、`projection.py`、`hands.py`、契約套件與少量測試），
範圍僅限下列 5 項；其餘已結案檔案與全部歷史證據未動。

### 採用的決策

1. 採用 P3-00，P2-A 風險 1、2 為必要前置。
2. 公開資料與事件 payload 以**組合＋精確型別白名單**加入，不改 `PublicGameData` 的既有欄位。
3. 固定牌序由測試專用受信任路徑注入；正式 `create_game` 仍拒絕 test-only；以靜態守衛防止應用程式碼誤用。
4. 一局＝單手牌（先做單手）。
5. 積分語意與盲注數值：採標準德州預設並標為**待人工確認**（短額 all-in 不重新開放加注、加注為「加到」；盲注金額、初始積分、燒牌尚未定，P3-01 前須提供）。

### 工作項目與結果

1. **P2-A 風險 1（修補，待驗收）**：`Deck.shuffle()`／`reset()` 改為在副本上洗牌、成功後才取代牌序；失敗（含 `BaseException`）時牌組進入不可用狀態，
   `deal()` 拋出 `DeckUnavailableError`，直到下一次 `reset()`／`shuffle()` 成功；新增 `is_available`；`require_production_deck` 拒絕不可用牌組。7 項新測試含「半途失敗不外露順序」。
2. **P2-A 風險 2（緩解，非根除）**：新增靜態守衛測試，掃描 `app/` 確認除 `deck.py` 定義處外沒有任何 `for_testing`／`*_for_testing` 使用；
   test-only 旗標與同程序竄改的信任限制**仍開放**。
3. **契約套件補三項缺口（並再擴充）**：錯誤訊息不得含隱藏牌（`repr` 與牌面碼，涵蓋驗證／套用／視圖／結果錯誤）、
   `apply_action`／`validate_action`／`get_player_view`／`calculate_result` 可重複且決定性、結束後須拒絕形式合法的動作（新增 `after_over` 場景欄位）、視圖擴充資料與狀態一致。
   故意寫壞的引擎由 13 種增至 **19 種**，全被抓到且各有對應失敗訊息。
4. **`HandRank` 語意驗證**：建構時拒絕不可能的牌力（2 高順子、單一點數葫蘆、非遞減同花等）。
   窮舉 oracle：各牌型被接受的 tiebreak 數量恰為 10／156／156／1277／10／858／858／2860／1277（合計 7462），與可達強度完全一致；另以隨機抽樣驗證建構子與判定一致。
5. **擴充機制**：新增 `core/extensions.py`（`PublicExtension`、`EventPayload`、`register_public_extension`、`register_event_payload`）。
   `GameState`／`PlayerView` 新增可選 `extension`，`GameEvent` 新增可選 `payload`（皆預設 `None`）；只接受已註冊、**精確型別**的 frozen＋slots dataclass，且須自行定義 `__post_init__`；
   子類別、未註冊類別、dict 一律拒絕。`project_player_view` 以 `replace()` 重建並重新驗證擴充資料，建構後被改寫的擴充資料會在投影時被拒絕。19 項測試。

### 與已結案契約的差異（須人工確認）

- `GameState`、`PlayerView`、`GameEvent` 各新增一個預設 `None` 的欄位；既有欄位、位置參數順序與 `PublicGameData` 不變。
- 兩個既有測試的呼叫點調整：`test_engine_contract.py`、`test_projection.py` 中的 `EventWithHand` 因新欄位 `payload` 位於額外欄位之前，原本第 5 個位置參數改為 `hand=` 關鍵字；測試意圖與斷言不變。
- 公開輸出（`asdict`／`repr`）會多出 `extension`／`payload` 欄位（內容為已註冊的公開型別）。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P3-00 extensions：exit 0；19 passed in 0.13s
- P3-00 deck failure and isolation：exit 0；7 passed in 0.12s
- P2-F projection：exit 0；15 passed in 0.13s
- P2-F contract suite：exit 0；23 passed in 0.26s
- P2-E texas hands：exit 0；55 passed in 3.20s
- P2-D registry：exit 0；34 passed in 0.15s
- P2-C engine contract：exit 0；28 passed in 0.16s
- R2 public field matrix：exit 0；25 passed in 0.11s
- R1 public isolation：exit 0；19 passed in 0.12s
- Original P2-B regression：exit 0；124 passed in 2.17s
- P2-A regression：exit 0；127 passed in 0.22s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.91s
- Mypy：exit 0；Success: no issues found in 34 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；41 files already formatted
- Full backend suite：exit 0；480 passed, 5 skipped, 1 warning in 7.43s
- pip check：exit 0；No broken requirements found.

新增測試：extensions 19、Deck 失敗與隔離 7、契約套件 +6（含 6 種新壞引擎）、`HandRank` +3，合計 +35；完整 backend **480 passed、5 skipped**（445＋35；5 項 PostgreSQL 測試仍未驗證通過）。
副本上 21 種變異（白名單、精確型別、凍結／slots／驗證檢查、投影重建、Deck 失敗關閉各環節、閘門、`HandRank` 語意）全部被抓到。
證據檔 `P3_00_TEST_EVIDENCE.json`；`deck.py` SHA-256 `06e62540a0eba17e4285a196497d831d5675913ffe3d57342e0c011f439fb40d`；`extensions.py` `f455f1a8c52e5cb1667801015a3c69f73530b0891daf864c053db41f5358cd71`；`hands.py` `d62ad4d0d81005ba1f6d5c202ca718a7011c35e4b8fab24fd971fcec6c18298e`；
`engine_contract_suite.py` `2d7f8ae9475d04ea4b1196ece6f190a96d0bd7acfc0a1032cefbafeb45c9b5ff`。B／R1／R2／C／D／E／F 證據未覆寫。

### 尚未解決的限制

- P2-A 風險 2 僅緩解：`Deck.for_testing` 仍可被同程序受信任程式呼叫；風險 3（同程序信任限制）、風險 4（歷史追溯）、PostgreSQL 5 項測試仍開放。
- 擴充註冊是受信任的啟動期程式碼，不防禦任意同程序程式；全域白名單在測試中會累積註冊。
- 契約套件仍只在 stub 上驗證；不涵蓋遊戲規則。
- 德州專屬公開資料、事件 payload、單手牌的完整狀態皆未定義（P3-01 起）；盲注金額、初始積分、燒牌待確認。
- Room、GameSession、認證、傳輸與資料庫整合仍未實作。P3-00 是否結案須人工獨立驗收。

---

## Phase 2 收尾決議 — CONDITIONAL（僅文件更新）

人工決議：Phase 2 以 **CONDITIONAL** 方式收尾，進入 Phase 3 規劃。P2-07 已勾選。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 Phase 3 實作，未做任何 Git 寫入。

### 收尾範圍

- 已結案階段：P2-A（CONDITIONAL PASS）、P2-B、P2-C、P2-D、P2-E、P2-F（皆 CONDITIONAL PASS，各自的保留條件見對應章節）。
- 最終回歸：**445 passed、5 skipped**；5 項 PostgreSQL 測試**尚未驗證通過**。

### 與 PRD 交付邊界的差異（須明確承接）

- PRD 的 Phase 2 交付包含 Room、GameSession 型別；規格未定義其欄位契約，**延後**，P2-03 保持未勾選並註明「部分完成」。
  須在 Phase 3 或 Phase 5 開始前決定歸屬。

### 帶入 Phase 3 的未解決事項（Phase 2 的風險總表仍然有效）

- P2-A 四項風險仍未完成；其中風險 1、2 為先前建議的 Phase 3 前置條件，是否採用由人工在 Phase 3 規劃中決定。
- 契約套件三項缺口（錯誤訊息洩漏、決定性、結束後動作）須在第一個真實引擎前補上。
- `HandRank` 語意驗證、`register()` 回傳值檢查、標準德州規則假設待確認。
- 正式認證、傳輸層、資料庫整合、真實引擎與正式發牌均未驗收。

---

## P2-F 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P2-F = **CONDITIONAL PASS**，核准 **P2-F 階段**（投影工具、共用契約套件、十三支擴充性驗證）結案。
**這不等於 Phase 2 整體完成**：P2-07 不勾選，Phase 2 整體是否收尾須人工另行決定。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 Phase 3，未做任何 Git 寫入。

### 驗收範圍與獨立複驗結果

- 範圍：`projection.py`、`engine_contract_suite.py` 及其測試、十三支擴充性與未登記不可啟用的測試、Phase 2 對帳與風險總表。
- 獨立複驗：`models.py`、`engine*.py`、`registry.py`、Card、Deck、`texas_holdem/`、migration、舊測試與 B／R1／R2／C／D／E 證據相對 HEAD 無差異；
  P2-F 證據來源雜湊、五份舊證據雜湊與 15 項檢查退出碼皆吻合。
- Backend：**445 passed、5 skipped**；5 項 PostgreSQL 測試**尚未驗證通過**。Mypy、Ruff、格式檢查通過。
- 對抗驗證：投影工具對建構後被改寫的 turn、版本、status、手牌皆在投影時重新驗證並拒絕；13 種壞引擎全被抓到。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件

1. **契約套件未檢查「錯誤訊息不洩漏」**：只驗證拒絕為 `GameError`，不檢查訊息是否含牌面（`models.py` 規定 message 必須可公開）。第一個真實引擎之前須補上。
2. **契約套件未檢查決定性**：從未對同一狀態重複套用同一動作，抓不到非決定性引擎（`engine.py` 規定除 create_game 外須為純函式）。
3. **「結束後不可再有動作」檢查太弱**：重用為進行中局面設計的 `illegal`，只對特定玩家放行的引擎可通過；須改為提供「結束後形式合法的動作」。
4. **通過套件不等於遵守完整契約**：獨立複驗另列 7 種未被偵測的壞引擎（含錯誤訊息洩漏、非決定性、結束後放行、跨局重用隱藏牌等），其中前三項為明文契約違規；其餘屬遊戲專屬規則或無法由套件強制。
5. **套件僅在 stub 上驗證**：真實引擎仍不存在；十三支只驗證 payload 型別可擴充，沒有任何規則。
6. 投影工具不是授權邊界；沿用 P2-B～P2-E 的信任限制。

### Phase 2 整體狀態（待人工決定）

- P2-03 部分完成（Room、GameSession 延後）；P2-07 未勾選。
- 進入 Phase 3 的建議前置條件仍為 P2-A 風險 1、2；完整風險總表見下方 P2-F 章節。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險。
- [ ] test-only Deck 與正式引擎的隔離。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口。

### 尚未驗收（P2-F 通過不代表已完成）

- Phase 2 整體完成與 P2-07。
- Room、GameSession 型別；真實遊戲引擎與正式發牌。
- 正式認證與授權、傳輸層、資料庫整合。
- 十三支、五張抽牌、大老二的規則或牌型；七選五與結算（P3-04）。
- PostgreSQL 測試（5 項 skipped）。

---

## P2-F 投影、共用契約套件與 Phase 2 整體驗收 — 已人工驗收（見上方結案決議）

日期：2026-11-15（Asia/Taipei）。依 5 項規劃決策（照建議）實作。
未實作 Room／GameSession、真實引擎、十三支規則、七選五、認證、傳輸或資料庫；未修補 P2-A 風險；未 commit。
**本節不是「Phase 2 完成」宣告**：Phase 2 以 CONDITIONAL 方式收尾，須由人工驗收，並以下方風險總表作為進入 Phase 3 的條件。

### 採用的決策

1. 投影工具為純函式預設實作，不是授權邊界；引擎仍可自訂 `get_player_view`（例如額外公開資訊，規格未定義）。
2. 共用契約測試套件現在建立，作為第一個真實引擎之前的必要條件。
3. 十三支只驗證擴充性，不寫規則；`chinese_poker` 維持未登記。
4. Room／GameSession 延後；P2-03 標為部分完成。
5. Phase 2 以「CONDITIONAL 結案＋風險總表」收尾；P2-A 風險 1、2 列為進入 Phase 3 的前置條件。

### 新增內容

- `backend/app/games/core/projection.py`：`project_player_view(state, viewer_id)`（從 `GameState` 重新建構公開與私有結構，重新執行精確型別驗證，因此也會抓到建構後被改寫的狀態；非成員回傳 `GameError`，不回顯 id；
  成員但無私有資料時回傳空手牌）與 `events_for_viewer(events, viewer_id)`（公開事件加寄給該玩家的私有事件，保持原順序）。
- `backend/tests/games/engine_contract_suite.py`：可重用的 `check_engine_contract`／`ContractScenario`，檢查 test-only 牌組被拒、
  狀態版本只加 1、拒絕不改狀態、事件序號跨步遞增、身分與規則版本不變、牌不重複且不超過 52 張、視圖只含本人手牌且不含他人手牌與剩餘牌、
  非成員無視圖、結束後的結果涵蓋全部玩家且積分守恆、新局不可已結束。
- 測試：`test_projection.py` 15 項、`test_engine_contract_suite.py` 17 項（合法引擎通過 1、**13 種故意寫壞的引擎全被抓到**、
  不同 payload 型別的中性 stub 通過同一套件並由 mypy 驗證 Protocol 相容、Registry 中 chinese_poker 等未實作遊戲查不到、Phase 1 目錄仍全部停用）。
- 投影模組另做 10 種變異驗證，全部被抓到。
- 修改：`core/__init__.py`（匯出）、`TASKS.md`、本檔。其他程式、舊測試與證據未改。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P2-F projection：exit 0；15 passed in 0.11s
- P2-F contract suite：exit 0；17 passed in 0.18s
- P2-E texas hands：exit 0；52 passed in 1.20s
- P2-D registry：exit 0；34 passed in 0.14s
- P2-C engine contract：exit 0；28 passed in 0.14s
- R2 public field matrix：exit 0；25 passed in 0.10s
- R1 public isolation：exit 0；19 passed in 0.10s
- Original P2-B regression：exit 0；124 passed in 2.01s
- P2-A regression：exit 0；127 passed in 0.19s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.87s
- Mypy：exit 0；Success: no issues found in 31 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；38 files already formatted
- Full backend suite：exit 0；445 passed, 5 skipped, 1 warning in 5.00s
- pip check：exit 0；No broken requirements found.

證據檔 `P2_F_TEST_EVIDENCE.json`；`projection.py` SHA-256 `1a0e3f8965f50921041a69e9d208f43a8b04525bdbda48dbbf385b58bbbea7e3`；`engine_contract_suite.py` `97c36f77546dd0f0f86ad6cf9a272b5fbe502ef446cba46aa7092d82feff16a4`；
`test_projection.py` `f99043a6b1d77b365dafd709cf8dc6accb643cedb1f238cb668612241d3230a8`；`test_engine_contract_suite.py` `0a582afbd251abbd2cc38110dfe170b8f3182be982c69e05f9278b7b519be854`。B／R1／R2／C／D／E 證據未覆寫。

### Phase 2 整體對帳（P2-01～P2-07）

| 項目 | 狀態 | 說明 |
| --- | --- | --- |
| P2-01 Card | 完成 | P2-A |
| P2-02 Deck | 完成（有開放風險） | P2-A；test-only 標記與重置風險見風險總表 |
| P2-03 型別 | **部分完成** | Player／Turn／GameAction／GameError／GameState／PlayerView／GameEvent／GameResult 已有；**Room、GameSession 未實作**（規格未定義欄位契約），留待後續階段 |
| P2-04 Protocol＋Registry | 完成 | P2-C、P2-D；真實引擎與共用套件驗證留待第一個引擎 |
| P2-05 德州五張牌型 | 完成 | P2-E；僅五張 |
| P2-06 投影契約＋十三支擴充 | 待驗收 | 本輪；十三支僅驗證擴充性，無規則 |
| P2-07 整體驗收 | 待驗收 | 本節；依 TASKS 原文「全階段功能到齊後才可勾選」，因 P2-03 部分完成，**不勾選**，待人工決定 |

各模組測試數：P2-A 127、P2-B 124＋R1 19＋R2 25、P2-C 28、P2-D 34、P2-E 52、P2-F 32、健康檢查 3，合計 444，另 1 項既有 migration 測試通過，
完整 backend **445 passed、5 skipped**（5 項 PostgreSQL 測試尚未驗證通過）。

### 未解決風險總表（進入 Phase 3 前須處理或明確接受）

**進入 Phase 3 的前置條件（建議）**
- [ ] P2-A 風險 1：reset() 安全亂數失敗後仍能繼續發牌。
- [ ] P2-A 風險 2：test-only Deck 與正式引擎的隔離（目前僅 `require_production_deck` 防誤用）。

**持續開放**
- [ ] P2-A 風險 3：Python frozen dataclass／同程序任意程式碼的信任限制（建構後改寫、copy／pickle、Enum 附加屬性、`_entries` 直接寫入）。
- [ ] P2-A 風險 4：完整回歸證據與程式版本的歷史追溯缺口。
- [ ] PostgreSQL 5 項測試尚未驗證通過。
- [ ] `HandRank` 可被直接建構出語意不可能的牌力（P2-E 保留條件）。
- [ ] `register()` 回傳值必須由呼叫端檢查；空 Registry 為 False（P2-D）。
- [ ] 事件沒有 payload；契約套件只涵蓋中繼資料層與卡牌守恆，不涵蓋遊戲規則。
- [ ] `GameState`／`PlayerView` 不重新驗證被事後修改的公開資料；本輪的投影函式在投影時會重驗，但不是全域保證。
- [ ] 標準德州規則假設仍待人工確認；七選五與結算屬 P3-04。

### 尚未驗收（P2-F 通過不代表已完成）

- Room、GameSession 型別。
- 真實遊戲引擎與正式發牌（契約套件只在 stub 上驗證）。
- 正式認證與授權（投影函式不驗證身分，viewer_id 須由已驗證的伺服器端上下文提供）。
- 十三支、五張抽牌、大老二的任何規則或牌型。
- 傳輸層（REST／WebSocket）與資料庫整合。P2-F 與 Phase 2 是否結案須人工獨立驗收。

---

## P2-E 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P2-E = **CONDITIONAL PASS**，核准**德州五張牌型階段**結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P2-F，未做任何 Git 寫入。

### 驗收範圍與獨立複驗結果

- 範圍：`texas_holdem/hands.py`（`HandCategory`、`HandRank`、`evaluate_five`、`compare`）與其測試；僅限五張。
- 獨立複驗：core 全部模組、migration、舊測試與 B／R1／R2／C／D 證據相對 HEAD 無差異；
  P2-E 證據 20 個來源雜湊、四份舊證據雜湊與 13 項檢查退出碼皆吻合。
- Backend：**413 passed、5 skipped**（361＋52）；5 項 PostgreSQL 測試**尚未驗證通過**。Mypy、Ruff、格式檢查通過。
- 獨立驗證：與實作不同寫法的參考比較器對 15 萬組隨機兩手牌比較，0 項不一致；
  重做列舉的各牌型不同強度為 10／156／156／1277／10／858／858／2860／1277，合計 7462，與公認數字相符。
- 副本變異 20 種：18 種被抓到，其餘 2 種為等價變異。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件

1. **`HandRank` 可被直接建構出語意不可能的牌力**：只驗證型別、值範圍 2～14 與長度；
   順子 `(2,)`、葫蘆 `(5,5)`、同花 `(2,3,4,5,6)`、同花順 `(3,)`、同花 `(9,9,9,9,9)` 皆被接受。
   `HandRank` 僅在由 `evaluate_five` 產生時可信；若日後接收外部傳來的 `HandRank`，須先加語意驗證或限制建構來源。
2. **規則採標準德州假設**：規格未逐項定義比較鍵、wheel 與皇家同花順；獨立驗證證明實作與標準規則一致，
   不證明規格要求的就是標準規則，仍須人工確認無地方規則。
3. **完整窮舉不在測試套件內**：僅記錄於證據檔 `manual_exhaustive_check` 的一次性結果（約 38 秒），無法在 CI 重現；
   日常測試只含組合數 oracle 與固定種子抽樣。
4. **牌力結果具敏感性**：只能在伺服器內部使用，目前沒有機制防止其進入公開資料或日誌，僅靠文件約束。
5. 沿用 P2-B～P2-D 保留條件：僅建構時驗證；真實引擎前須先建立共用契約測試套件。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險。
- [ ] test-only Deck 與正式引擎的隔離。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口。

### 尚未驗收（P2-E 通過不代表已完成）

- 七選五、平分池與餘數、結算（P3-04）。
- 大老二、十三支、五張抽牌的牌型。
- 真實遊戲引擎與正式發牌；共用契約測試套件；Registry 目前實際為空。
- 正式認證與授權、玩家資料投影、私有資訊投影契約（P2-F）。
- Phase 2 整體驗收（P2-F）；PostgreSQL 測試（5 項 skipped）。

---

## P2-E 德州五張牌型辨識 — 已人工驗收（見上方結案決議）

日期：2026-11-15（Asia/Taipei）。依盤點報告「照建議」實作。
只做德州**五張**牌型純函式；未做七選五、結算、下注、大老二、十三支、五張抽牌；未接 Registry 或引擎；
未開始 P2-F；未修改 Card／Deck／core 模組／migration；未 commit。

### 採用的決策（對應盤點第 6 節）

1. 只做五張；七選五留 P3-04。
2. 比較鍵採標準德州規則（規格未逐項定義，已列為需人工確認的假設）。
3. wheel 為 5 高順子；A 只在 A2345 為低牌；不允許環繞（QKA23、JQKA2 非順子）。
4. 皇家同花順＝A 高同花順，不另設牌型。
5. 花色只決定是否為同花／同花順，同牌型比較完全不看花色。
6. 輸出僅 `HandRank(category, tiebreak)`，平手為 `compare == 0`；不附選中的牌。

### 介面

位置 `backend/app/games/texas_holdem/hands.py`：

- `HandCategory`（九種）、`HandRank`（精確型別驗證：category、tiebreak 為精確 int tuple、值 2～14、長度與牌型相符）。
- `evaluate_five(cards)`：只接受精確 `tuple` 的 5 張精確 `Card`、無重複；錯誤輸入拋例外（程式錯誤）。
- `compare(a, b)`：回傳 -1／0／1，只接受精確 `HandRank`。
- 強度與點數值使用明確對照表，不依賴 `Rank`／`Suit`／`HandCategory` 宣告順序。
- 靜態只依賴 `app.games.core.card`（以 AST 測試驗證）；執行期因套件 `__init__` 會載入整個 `core`。

牌型與比較鍵：同花順(高牌)、鐵支(四條, 踢腳)、葫蘆(三條, 一對)、同花(五張降序)、順子(高牌)、
三條(三條, 兩踢腳)、兩對(大對, 小對, 踢腳)、一對(對子, 三踢腳)、高牌(五張降序)。

### 修改檔案

- 新增：`backend/app/games/texas_holdem/__init__.py`、`hands.py`、`backend/tests/games/test_texas_hands.py`、`docs/reports/P2_E_TEST_EVIDENCE.json`。
- 修改：`TASKS.md`、本檔。其他程式與證據未改。

### 新增測試（52 項）與獨立 oracle

九種牌型 15 個案例的類別與比較鍵、無環繞、26 手代表牌的嚴格全序、六組跨花色平手、輸入牌序與花色置換不變（含全部 120 種排列與 24 種花色置換）、
張數錯誤、容器子類別／list／字串／iterator、`Card` 子類別與非 Card 元素、重複牌、`HandRank` 欄位驗證、結果不可變、
`compare` 型別檢查、強度與宣告順序無關、AST 依賴檢查。

Oracle（不重跑整個牌空間、以組合數推導）：以點數多重集合列舉並用組合數計權重，驗證各牌型數量
40／624／3,744／5,108／10,200／54,912／123,552／1,098,240／1,302,540，總數 2,598,960，不同強度 7,462；
另以固定種子抽 20,000 手具體牌，驗證與同點數多重集合的代表牌結果一致。
**另做一次性的完整窮舉**（不在測試套件內，約 38 秒）：枚舉全部 2,598,960 手，各牌型數量與 7,462 皆與公認數字相符，結果記錄於證據檔 `manual_exhaustive_check`。
窮舉耗時過長，未納入日常測試（盤點報告原本建議納入，此為差異）。

變異測試（副本上 20 種）：18 種被抓到；另 2 種（`ordered[:4]`、`ordered[:3]` 切片）為**等價變異**
（該陣列長度本來就是 4 與 3，改動不改變行為），不是測試缺口。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P2-E texas hands：exit 0；52 passed in 1.19s
- P2-D registry：exit 0；34 passed in 0.13s
- P2-C engine contract：exit 0；28 passed in 0.14s
- R2 public field matrix：exit 0；25 passed in 0.09s
- R1 public isolation：exit 0；19 passed in 0.10s
- Original P2-B regression：exit 0；124 passed in 2.16s
- P2-A regression：exit 0；127 passed in 0.19s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.86s
- Mypy：exit 0；Success: no issues found in 27 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；34 files already formatted
- Full backend suite：exit 0；413 passed, 5 skipped, 1 warning in 5.06s
- pip check：exit 0；No broken requirements found.

證據檔 `P2_E_TEST_EVIDENCE.json`；`hands.py` SHA-256 `dfde66c70ff8f6a233cf2dfa0d5e9c96eaa99f7a0e32abd48ce6aa3ce6be72f3`；`test_texas_hands.py` `d19af162f46ac4fd8c5bd169e7bcba685ab38ea2e5c6a7ceb3c2ddbed3f79f68`。
B／R1／R2／C／D 證據未覆寫。

### 尚未解決的限制

- 規格未逐項定義比較鍵、wheel 細節與皇家同花順：目前採標準德州規則，仍需人工確認這是預期，而非另有地方規則。
- 只處理五張；七選五、平分池與餘數、結算屬 P3-04。
- 結果揭露牌力，僅限伺服器內部使用，不得進入公開資料或日誌。
- P2-A 四項風險、P2-C 共用契約測試套件、P2-D Registry 尚無真實引擎、PostgreSQL 5 項測試皆未解決。
- 正式發牌、玩家投影與認證仍未驗收。P2-E 是否結案須人工獨立驗收。

---

## P2-D 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P2-D = **CONDITIONAL PASS**，核准 **Registry 機制階段**結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P2-E～P2-F，未做任何 Git 寫入。

### 驗收範圍與獨立複驗結果

- 範圍：`registry.py`（`EngineRegistration`、`EngineRegistry`）及其測試。
- 獨立複驗：`models.py`、`engine.py`、`engine_types.py`、Card、Deck、migration、舊測試與 B／R1／R2／C 證據相對 HEAD 無差異；
  P2-D 證據 17 個來源雜湊、R1／R2／P2-C 證據雜湊與 12 項檢查退出碼皆吻合。
- Backend：**361 passed、5 skipped**（327＋34）；5 項 PostgreSQL 測試**尚未驗證通過**。Mypy、Ruff、格式檢查通過。
- 對抗驗證：全形字元、阿拉伯數字、尾端換行 code 被拒；重複不覆蓋；錯誤訊息不回顯輸入；副本上 10 種變異全被抓到。
- 歷史紀錄與各階段證據皆保留，未覆寫。

### 保留條件

1. **`register()` 的失敗結果可被忽略**：成功回傳 `None`、重複回傳 `GameError`；呼叫端（組裝層）**必須檢查回傳值**，否則重複登記會被默默吞掉，Python 與 mypy 都不會警告。
2. **空 Registry 在布林判斷為 False**（定義了 `__len__`）：不得用 `registry or EngineRegistry()` 這類寫法；應以 `is None` 判斷。
3. **執行期方法檢查可被繞過**：只定義 `__getattr__` 回傳可呼叫物件的引擎可通過；登記後改寫引擎方法不會重新檢查。檢查只確認存在且可呼叫，不驗證簽章或語意。
4. **內部狀態未封閉**：直接寫入 `registry._entries` 可繞過驗證（屬 P2-B 已記載的同程序任意程式碼信任限制）。
5. 登記不是執行緒安全，僅限啟動階段登記、之後視為唯讀。
6. 沿用 P2-B／P2-C 保留條件：僅建構時驗證；真實引擎前須先建立共用契約測試套件。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險。
- [ ] test-only Deck 與正式引擎的隔離。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口。

### 尚未驗收（P2-D 通過不代表已完成）

- 真實遊戲引擎與正式發牌；Registry 目前實際為空。
- 共用契約測試套件。
- 「資料庫 enabled 且已登記才可玩」的交集（組裝層）。
- 正式認證與授權、玩家資料投影。
- 牌型辨識（P2-E）、Phase 2 整體驗收（P2-F）。
- PostgreSQL 測試（5 項 skipped）。

---

## P2-D Engine Registry — 已人工驗收（見上方結案決議）

日期：2026-11-15（Asia/Taipei）。依 5 項規劃決策（照建議）實作純記憶體 Registry。
未實作任何真實遊戲、未建立假引擎進正式模組、未連資料庫、未改 migration；未開始 P2-E／P2-F；未 commit。

### 採用的決策

1. `EngineRegistry` 為一般實例，無模組層全域單例；由未來組裝層於啟動時建立並登記。
2. 預期內拒絕（重複／未知 code）回傳 `GameError`（`duplicate_game`、`unknown_game`）；不合規的登記（錯誤 code、人數、非引擎物件）拋例外。未知 code 不會被寫進錯誤訊息。
3. Registry 不讀資料庫，只提供 `is_registered`；可玩 = 資料庫 `enabled` 且 Registry 已登記，由組裝層取交集。
4. Registry 不保存 `enabled` 旗標；「未實作遊戲不可啟用」以「未登記即查不到」表達。
5. 登記記錄帶 `min_players`／`max_players`（2 ≤ min ≤ max，與資料庫 CHECK 一致），但不與資料庫比對。

### 契約與欄位矩陣

| 項目 | 精確型別／規則 | 驗證入口 |
| --- | --- | --- |
| EngineRegistration.code | `str`，`[a-z][a-z0-9_]{1,31}`（fullmatch，對應 game_types.code 32 字） | `__post_init__` |
| rules_version | `str` 非空白 | 同上 |
| min_players／max_players | `int`（非 bool），min ≥ 2，max ≥ min | 同上 |
| engine | 必須是實例（非 class），六個方法皆存在且可呼叫 | 同上（執行期檢查，補 Protocol 靜態限制） |
| register(registration) | 精確 `EngineRegistration`；重複回傳 GameError，不覆蓋 | `register` |
| get／is_registered(code) | 精確 `str`（非 str 拋 TypeError）；未知回傳 GameError | 各方法 |
| codes()／registrations() | 排序的不可變 tuple 快照 | — |

### 修改檔案

- 新增：`backend/app/games/core/registry.py`、`backend/tests/games/test_registry.py`、`docs/reports/P2_D_TEST_EVIDENCE.json`。
- 修改：`backend/app/games/core/__init__.py`（匯出）、`TASKS.md`、本檔。`models.py`、`engine.py`、`engine_types.py`、Card、Deck、migration 未改。

### 新增測試（34 項）與不適用項目

空 Registry 與四個資料庫目錄 code 皆未登記、登記與查詢往返、重複不覆蓋、未知不回顯輸入、
非 exact str 的查詢、10 種格式錯誤 code 與長度邊界、10 種非法中繼資料（子類別、bool、float、範圍）、
六個方法逐一缺失／不可呼叫、class 與 None 當引擎、登記物件子類別、快照不外洩內部狀態與 `__slots__`、
實例互相獨立、模組不匯入框架或 `app.db`。不適用：資料庫 enabled 旗標（刻意不存在）、執行緒安全（僅啟動期登記）。
另在副本上做 10 種變異驗證（覆蓋重複、回顯 code、match 取代 fullmatch、移除方法檢查、允許 class、移除人數檢查、
放寬型別、未排序等），全部被測試抓到。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P2-D registry：exit 0；34 passed in 0.13s
- P2-C engine contract：exit 0；28 passed in 0.15s
- R2 public field matrix：exit 0；25 passed in 0.09s
- R1 public isolation：exit 0；19 passed in 0.11s
- Original P2-B regression：exit 0；124 passed in 2.02s
- P2-A regression：exit 0；127 passed in 0.19s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.87s
- Mypy：exit 0；Success: no issues found in 24 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；31 files already formatted
- Full backend suite：exit 0；361 passed, 5 skipped, 1 warning in 3.64s
- pip check：exit 0；No broken requirements found.

證據檔 `P2_D_TEST_EVIDENCE.json`；`registry.py` SHA-256 `0ec96c474810f5a3f73cc22ef0c97fb6e0d94218ce6cf85778988fb56a539d6d`；`test_registry.py` `0ed88d81e9567f55a994f5de139e1d69bf2cc607fba1b5665ecdfd037eb331cb`。
R1／R2／P2-C／原始證據未覆寫。

### 尚未解決的限制

- 目前沒有真實引擎，Registry 在實際應用中為空；本輪只驗證機制。
- 執行期檢查只確認方法存在且可呼叫，不驗證簽章或語意；仍需 P2-C 保留條件 1 的共用契約測試套件（建議在第一個真實引擎前完成）。
- 登記不是執行緒安全；僅限啟動階段登記，之後視為唯讀。
- 與資料庫目錄的交集（可玩 = enabled ∧ 已登記）尚未實作，屬組裝層。
- P2-A 四項風險仍開放；認證、玩家投影、真實引擎與正式發牌仍未驗收。P2-D 是否結案須人工獨立驗收。

---

## P2-C 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P2-C = **CONDITIONAL PASS**，核准**契約階段**結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試或證據，未開始 P2-D～P2-F，未做任何 Git 寫入。

### 驗收範圍與獨立複驗結果

- 範圍：`engine.py`（GameEngine Protocol、`require_production_deck`）、`engine_types.py`（結果與事件型別）及其契約測試。
- 獨立複驗：`models.py`、Card、Deck、migration 與 R1／R2／原始證據相對 commit 無差異；P2-C 證據 15 個來源雜湊與 11 項檢查退出碼皆吻合。
- Backend：**327 passed、5 skipped**（共 332）；5 項 PostgreSQL 相關測試**尚未驗證通過**。
- 對抗驗證：副本上 14 種變異（移除 test-only／完整牌組／序號連續／收件人／守恆／重複 id／精確型別等檢查）全部被測試抓到；
  mypy strict 能拒絕缺方法或回傳型別錯誤的引擎；兩個新模組未匯入 fastapi／sqlalchemy 等框架。
- 歷史紀錄與 R1／R2／P2-C 證據皆保留，未覆寫。

### 保留條件

1. **契約僅在型別層強制**：Protocol 無執行期檢查；「version＋1」「視圖不含他人牌」只由測試專用 stub 示範。
   真實引擎開始前須建立可重用的共用契約測試套件，否則不得視為已遵守契約。
2. **部分不變式無法由型別驗證**：`ApplyResult` 不知前一狀態、無法驗證版本遞增；`GameResult` 不驗證玩家屬於該局；
   `GameConfig.game_type` 不與 `GameState.game_type` 核對；名次允許並列。
3. **`require_production_deck` 只防誤用**：只檢查進入時狀態；引擎若未抽空牌組，同一副牌可跨局重用；
   test-only 旗標可被同程序程式碼改寫（屬 P2-A 開放風險）。
4. **事件沒有 payload**：私有事件的可見性隔離僅在中繼資料層，實際 payload 的保密留待真實引擎。
5. **測試較弱處**：視圖不洩漏測試為公開資料文字的牌面碼字串比對，不是結構性證明。
6. 沿用 P2-B 信任限制（僅建構時驗證；copy／pickle／反射不重驗）。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險。
- [ ] test-only Deck 與正式引擎的隔離。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口。

### 尚未驗收（P2-C 通過不代表已完成）

- 真實遊戲引擎與正式發牌。
- 正式認證與授權。
- 玩家資料投影（`get_player_view` 目前僅有契約與 stub 示範）。
- Registry（P2-D）、牌型辨識（P2-E）、Phase 2 整體驗收（P2-F）。
- PostgreSQL 測試（5 項 skipped）。

---

## P2-C 六方法 GameEngine Protocol — 已人工驗收（見上方結案決議）

日期：2026-11-15（Asia/Taipei）。依 6 項規劃決策（照建議）實作契約層。
只建立 Protocol、結果型別、牌組來源規則與契約測試；**未**實作任何真實遊戲、Registry、牌型辨識、
玩家投影、認證或 WebSocket；未開始 P2-D～P2-F，未修改 Card／Deck／models.py／migration。未 commit。

### 採用的決策

1. 動作 payload：`GameAction` 不變，Protocol 以泛型 `PayloadT` 接收各引擎自訂 payload，不接受任意 dict。
2. 牌組來源：`create_game` 接收 `Deck`，以 `require_production_deck` 拒絕非精確 Deck、test-only、非完整未發牌牌組（不是防竄改機制）。
3. 錯誤：預期內拒絕回傳 `GameError`；程式錯誤才拋例外（test-only 牌組為 `TestOnlyDeckError`）。
4. 新型別放在新模組 `engine_types.py`，`models.py` 未改。
5. 事件分 PUBLIC／PRIVATE：PUBLIC 不可有 recipient，PRIVATE 必須有且須屬於該局玩家。
6. `GameResult` 只含各玩家 `points_delta` 與 `rank`，積分變化總和必為 0。

### 契約與欄位矩陣

| 方法 | 輸入 | 輸出 |
| --- | --- | --- |
| create_game | GameConfig、session_id、players tuple、Deck | GameState｜GameError |
| validate_action | GameState、GameAction、PayloadT | ActionValidation（不改狀態） |
| apply_action | GameState、GameAction、PayloadT | ApplyResult｜GameError（version＋1，事件連續） |
| get_player_view | GameState、viewer_id | PlayerView｜GameError（只含 viewer 私有資料） |
| is_game_over | GameState | bool |
| calculate_result | GameState | GameResult｜GameError（未結束回錯誤） |

新型別欄位：GameConfig（str、str）、GameEvent（int≥0、str、EventVisibility、UUID｜None）、
ActionValidation（GameError｜None）、ApplyResult（GameState、精確 tuple[GameEvent]，seq 連續）、
PlayerResult（UUID、有號 int、int≥1）、GameResult（精確 tuple[PlayerResult]，id 不重複、總和 0）。
全部沿用 P2-B 的 `type(x) is X` 精確型別驗證，子類別一律拒絕。

### 修改檔案

- 新增：`backend/app/games/core/engine.py`、`engine_types.py`、`backend/tests/games/test_engine_contract.py`、`docs/reports/P2_C_TEST_EVIDENCE.json`。
- 修改：`backend/app/games/core/__init__.py`（匯出）、`TASKS.md`、本檔。

### 新增測試（28 項）與不適用項目

涵蓋型別矩陣（16 個非法值案例）、PlayerResult／GameResult 的容器子類別、巢狀非法值、重複與守恆、
ApplyResult 事件連續與 recipient、帶 `hand` 的 GameEvent 子類別、牌組來源規則（含說謊的 Deck 子類別）、
以測試專用 stub 引擎驗證六方法（拒絕為資料、validate／view 不改狀態、version 與事件遞增、積分守恆、
視圖不含他人手牌與剩餘牌），以及兩個新模組不匯入 fastapi／sqlalchemy 等框架。
不適用：真實牌型、下注、認證、傳輸（後續階段）。stub 引擎只存在於測試，不進 Registry。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。
- P2-C engine contract：exit 0；28 passed in 0.14s
- R2 public field matrix：exit 0；25 passed in 0.09s
- R1 public isolation：exit 0；19 passed in 0.10s
- Original P2-B regression：exit 0；124 passed in 2.04s
- P2-A regression：exit 0；127 passed in 0.18s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.86s
- Mypy：exit 0；Success: no issues found in 22 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；29 files already formatted
- Full backend suite：exit 0；327 passed, 5 skipped, 1 warning in 3.56s
- pip check：exit 0；No broken requirements found.

P2-C 28＋R2 25＋R1 19＋原 P2-B 124＋P2-A 127＋健康檢查 3＝326；完整 backend 為 327 passed、5 skipped
（5 項 PostgreSQL 測試仍未驗證通過；差額 1 項為健康檢查以外的既有測試）。
證據檔 `P2_C_TEST_EVIDENCE.json` 的 `started_at` 已在檢查前取得（修正 R2 的順序問題）；
`engine.py` SHA-256 `929f66a982864f650b2fbecab677b1693099f18c84617f1a4886877ebb0f5c05`；`engine_types.py` `381d50765f472f741c8099140bbd69a6b76a331544f4dced23dc37de7ecb712c`；
`test_engine_contract.py` `e504f0907c34a22c72f4e343c36b4157acb37a12651978a4fcc233eb4d14d9d0`。R1／R2／原始證據未覆寫。

### 尚未解決的限制

- 型別與 Protocol 只描述契約；沒有真實引擎，契約的語意（例如「version＋1」「view 不含他人牌」）僅由 stub 測試示範，
  真實引擎須各自通過同樣測試。
- `require_production_deck` 只防誤用，不證明牌組已安全洗牌，也不防同程序竄改；P2-A 四項風險仍開放。
- 事件目前只有中繼資料，沒有 payload；payload 與其可見性隔離留待引擎／P2-F。
- 沿用 P2-B 信任限制：僅建構時驗證，copy／pickle／反射不重驗。
- 正式認證、玩家資料投影、遊戲引擎與正式發牌仍未驗收；P2-C 是否結案須人工獨立驗收。

---

## P2-B 正式結案決議 — CONDITIONAL PASS（僅文件更新）

人工驗收決議：P2-B = **CONDITIONAL PASS**，核准**純型別階段**結案。
本次只更新 `TASKS.md` 與本檔；未修改程式、測試、migration 或任何證據檔，未開始 P2-C～P2-F，未做任何 Git 寫入。

### 驗收範圍

- 範圍僅限 `backend/app/games/core/models.py` 的純資料型別契約與公開欄位精確型別驗證。
- 歷史紀錄完整保留：原 P2-B 驗收 FAIL → R1 修補 → R2 修補（公開欄位精確型別矩陣）→ 獨立複驗 → 人工 CONDITIONAL PASS。
- 證據檔 `P2_B_TEST_EVIDENCE.json`、`P2_B_R1_TEST_EVIDENCE.json`、`P2_B_R2_TEST_EVIDENCE.json` 皆保留，未覆寫。

### Backend 複驗結果

- 最終獨立複驗：`backend/tests` 共 **299 passed、5 skipped**。
- 5 項 skipped 為需要 `TEST_DATABASE_URL` 的 PostgreSQL 測試，**尚未驗證通過**，不得視為已通過。
- R2 證據的 298 passed 為選定無資料庫測試：R2 25＋R1 19＋原 P2-B 124＋P2-A 127＋健康檢查 3。
- Mypy（strict）、Ruff、格式檢查、相依檢查皆通過。

### 保留條件與信任限制

以下限制不阻擋純型別結案，後續階段不得假設其已解決：

1. **同程序任意 Python 程式碼（類別 B）**：`object.__setattr__`、反射、猴子補丁可在建構後修改 frozen 物件；
   事後修改的公開容器執行 `asdict()` 會保留子類別值（`repr` 因型別而不一定顯示）。P2-B 不宣稱是 Python 安全沙箱。
2. **`copy.copy` 與 pickle**：重建物件不會執行 `__post_init__`；對不受信任的 pickle 資料不得視為邊界，惡意 payload 未測試。
3. **Enum 附加屬性**：`GameStatus` 成員為全域單例，可被附加屬性；該屬性不出現在 `asdict()`／`repr()` 輸出，但屬共享可變狀態。
4. **`GameState`／`PlayerView` 不重新驗證**：`models.py` 中兩者只檢查 `PublicGameData` 的精確型別，
   不會重驗已被事後修改的公開資料（已實測被接受）。正常建構路徑不受影響。
5. **R2 證據時間戳順序**：`P2_B_R2_TEST_EVIDENCE.json` 頂層 `started_at` 為 `2026-11-15T19:57:46.722851+08:00`，
   晚於第一項檢查開始時間（`19:57:34`）。原因是證據產生腳本在檢查執行後才取該時間戳。
   依規定保留原始數值、不修改；命令、退出碼與結果不受影響。
6. 無 commit 可比對；修補前行為僅以重現紀錄為準。

### P2-A 持續開放事項（仍未完成）

- [ ] reset() 安全亂數失敗後仍能繼續發牌的風險。
- [ ] test-only Deck 與正式引擎的隔離。
- [ ] Python frozen dataclass／同程序任意 Python 程式碼的信任限制。
- [ ] 完整回歸證據與程式版本的歷史追溯缺口。

### 尚未驗收（P2-B 通過不代表已完成）

- 正式認證與授權。
- 玩家資料投影（PlayerView 目前僅為資料容器，不是授權邊界）。
- 遊戲引擎。
- 正式發牌。
- PostgreSQL 測試（5 項 skipped）。

---

## P2-B-R2 公開資料邊界完整修補 — 已人工驗收（見下方結案決議）

日期：2026-11-15（Asia/Taipei）。P2-B 第二次獨立複驗發現 `DisplayNameWithHand` 洩漏。
本輪只做 R2 修補與測試，**不自行宣告 P2-B 結案**；未開始 P2-C～P2-F，
未新增認證、WebSocket、正式玩家投影或遊戲引擎，未修改 Card、Deck、Phase 1 migration。

### 原始漏洞與重現方式

R1 只對模型類別做精確型別檢查，欄位值仍用 `isinstance`（`_text`、`_uuid`、`_tuple_of`）。
`class DisplayNameWithHand(str)` 附帶 `hand` 等任意屬性，可作為 `display_name` 通過
`Player` 與 `PublicGameData` 驗證並被原樣保留（修補前實測：`ACCEPTED`，物件 `__dict__` 含 `hand`）。
問題不在欄位名稱，而在「值型別可為子類別」；因此不採 `hand` 黑名單。

### 公開欄位完整矩陣

| 模型.欄位 | 允許的精確型別 | 巢狀結構 | 驗證入口 | `asdict()`／`repr()` 結果 |
| --- | --- | --- | --- | --- |
| Player.id | `UUID` | 無 | Player.__post_init__；PublicGameData 重驗 | 原 UUID／標準 repr |
| Player.display_name | `str`（非空白） | 無 | 同上 | 原 str |
| Player.seat | `int`（非 bool，≥0） | 無 | 同上 | 原 int |
| Player.points | `int`（非 bool，≥0） | 無 | 同上 | 原 int |
| Turn.player_id | `UUID` | 無 | Turn.__post_init__；PublicGameData 重驗 | 原 UUID |
| PublicGameData.status | `GameStatus`（Enum 有成員不可被繼承） | 無 | PublicGameData.__post_init__ | 原 Enum 成員 |
| PublicGameData.state_version | `int`（非 bool，≥0） | 無 | 同上 | 原 int |
| PublicGameData.players | 精確 `tuple` | 元素為精確 `Player`，其欄位逐一重驗 | 同上 | tuple of dict |
| PublicGameData.turn | `Turn` 或 `None` | 精確 Turn，player_id 重驗並須屬於 players | 同上 | dict 或 None |
| GameError.code／message | `str` | 無 | GameError.__post_init__ | 原 str |
| GameError.request_id | `UUID` 或 `None` | 無 | 同上 | 原 UUID／None |
| GameAction.player_id／request_id | `UUID` | 無 | GameAction.__post_init__ | 原 UUID |
| GameAction.state_version／type | `int`／`str` | 無 | 同上 | 原值 |

所有欄位皆無法由子類別攜帶額外屬性：值型別一律 `type(x) is X`，無任何欄位保留 isinstance 寬鬆檢查。
私有模型（PrivatePlayerData／PrivateGameData）本來就非公開，其 tuple 容器同樣改為精確 `tuple`，元素檢查未變。

### 方案比較與採用方案

| 方案 | 評估 | 決定 |
| --- | --- | --- |
| 精確型別拒絕 | 所有欄位值 `type(x) is X`；一般資料行為與參照不變；明確 TypeError；無轉換 | 採用 |
| 值正規化（`str(x)`、`UUID(int=…)`） | 需複製並決定失敗語意，改變物件參照；`str(subclass)` 仍可被惡意 `__str__` 影響 | 不採用 |
| 白名單序列化 | 會成為新的輸出契約並新增傳輸介面，超出本輪授權 | 不採用，也**不宣稱**任意 `asdict()` 已安全 |

`asdict()`／`repr()` 的安全性來自「公開資料物件只可能含精確型別欄位」的建構期驗證，
而非序列化函式本身；對未經此驗證的任意物件呼叫 `asdict()` 仍不安全。

### 修改檔案

- `backend/app/games/core/models.py`：`_uuid`／`_text`／`_tuple_of` 改精確型別；新增 `_check_status`、`_check_public_player`；PublicGameData 對每個 Player 欄位與 Turn.player_id 重驗。
- `backend/tests/games/test_public_field_matrix.py`（新增）。
- `docs/reports/P2_B_R2_TEST_EVIDENCE.json`（新增；R1／原始證據未覆寫）。

### 新增測試（25 項）

DisplayNameWithHand（建構與繞過 Player 驗證兩種入口）、10 個 Player 欄位非法值／子類別（各驗兩個入口）、
Turn.player_id UUID 子類別、status／state_version、tuple 子類別與串列與巢狀 tuple 與 None 元素、
Turn 型別錯誤、GameError／GameAction 的 7 個子類別案例、合法資料相容性與 asdict／repr 檢查。
不適用：Enum 子類別（有成員的 Enum 無法繼承，以測試證明）；非 hand 名稱的 sensitive 欄位以 `vault`／`secret` 涵蓋。

### 實際結果

環境：3.12.10，Windows-11-10.0.26300-SP0，PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1，無 HEAD。
- R2 public field matrix：exit 0；25 passed in 0.09s
- R1 public isolation：exit 0；19 passed in 0.10s
- Original P2-B regression：exit 0；124 passed in 2.01s
- P2-A regression：exit 0；127 passed in 0.17s
- Phase 1 no-database health：exit 0；3 passed, 1 warning in 0.89s
- Mypy：exit 0；Success: no issues found in 19 source files
- Ruff check：exit 0；All checks passed!
- Ruff format check：exit 0；26 files already formatted
- pip check：exit 0；No broken requirements found.

R2 25＋R1 19＋原 P2-B 124＋P2-A 127＋健康檢查 3＝298 passed，0 failed，0 skipped。
證據檔 `docs/reports/P2_B_R2_TEST_EVIDENCE.json`（含完整命令與輸出）；R1 證據 SHA-256 `a3569aa7e7fee90199d1b9e1304813a6a9ce25cd50958a444e6e350fbb94e5ca`，原始證據 `07d214ddf1f6a6a4f034ead576370aa9c51e1d5b44656162f3340191a9528fd8`。
`models.py` SHA-256：`1dcd0686ea00c75b779d9d552a2791613f8abc5c0ef5255326ddbadc73bc544d`；
`test_public_field_matrix.py` SHA-256：`102e2ebfd88970cc9f55ade3cbc26988e6a8577ac0a9a5fcb0ce8f958fa9dd70`。

### 尚未解決的限制

- 這不是 Python 安全沙箱：`object.__setattr__`、反射、猴子補丁可在建構後改寫 frozen 物件；PublicGameData 只保證建構當下的欄位值。
- 未提供正式玩家投影、授權、傳輸序列化；`asdict()` 的安全性僅限已通過驗證的公開模型。
- 無 commit 可比對，修補前行為以本輪重現紀錄為準；本輪未對修補前程式碼重跑新測試。
- P2-B 是否結案須人工獨立複驗。

---

## P2-B-R1 公開資料隔離修補 — 待人工複驗

日期：2026-11-15（Asia/Taipei）。P2-B 原獨立驗收為 **FAIL**。
本輪只完成 R1 最小修補與選定測試，**不自行宣告 P2-B 正式結案**。
未開始 P2-C～P2-F，未接入正式發牌、認證、WebSocket 或遊戲引擎。

### 【確認】唯讀盤點及原始漏洞

- 分支仍為 `feature/phase-1-foundation`，repository 無任何 commit，沒有可解析的 HEAD。
  初始 64 份專案檔都是未提交成果，以 SHA256 快照保留；未做任何 Git 寫入操作。
- 已閱讀 models.py、原 test_models.py、七份根規格、TASKS、P2-B 內部契約、原始報告及證據。
- 修補前實際重現 PlayerWithHand：公開容器保留該子類別，asdict 含手牌，repr 顯示 hand。
  原因是 `_tuple_of(..., Player, ...)` 只做 isinstance，子類別額外欄位會被 dataclass 遞迴保留。

修補前實際輸出：

```text
retains_subclass= PlayerWithHand
asdict_hand= ({'rank': <Rank.ACE: 'A'>, 'suit': <Suit.SPADES: 'S'>},)
repr_contains_hand= True
```

### 方案比較與採用的最小修補

| 方案 | 契約與影響 | 決定 |
| --- | --- | --- |
| 拒絕子類別 | 只接受精確公開模型型別，明確 TypeError；一般 Player 的欄位與物件參照不變，不自動轉換外部資料 | 採用 |
| 轉換為白名單公開 DTO | 必須新增 id／display_name／seat／points 的複製及重新驗證契約，改變物件參照，並處理來源屬性讀取與失敗語意 | 本輪不實作 |

新增私有 `_exact_type()`：以 `type(value) is expected` 驗證，不依賴 isinstance、frozen、
型別註記或 repr=False 作為子類別隔離機制。錯誤只包含欄位及預期型別，不輸出輸入物件或手牌。

套用位置：

1. PublicGameData.players：每項都必須是精確 Player，拒絕 PlayerWithHand 等擴充模型。
2. 同一公開資料鏈的 Turn 與 PublicGameData：拒絕額外私有欄位由相鄰公開模型入口帶入。
3. GameState.public／PlayerView.public：拒絕 PublicGameData 子類別，即使子類別覆寫並略過父類驗證。

一般合法 Player、tuple、Turn 不被複製、不被修改；既有資料欄位、玩家順序、空集合、
dataclasses.replace 及物件參照保持相容。沒有新增 DTO、自動清理／轉換或通用序列化流程。
Player 子類別仍可作為受信任程式的其他物件建立，但不能被公開容器接受；
子類別不屬於受支援的公開 DTO。這不是對任意 Python 程式碼的安全沙箱。

### 修改檔案

修改：

- `backend/app/games/core/models.py`：精確公開型別檢查，未變更遊戲規則或其他資料欄位。
- `backend/app/games/README.md`：補充拒絕子類別契約與錯誤語意。
- `TASKS.md`：記錄原驗收 FAIL、R1 實作／測試與待人工複驗狀態。
- `docs/reports/PHASE_2.md`：新增本修補紀錄，保留修補前歷史。

新增：

- `backend/tests/games/test_public_isolation.py`：19 項修補測試。
- `docs/reports/P2_B_R1_TEST_EVIDENCE.json`：本輪獨立證據。

未修改 card.py、deck.py、Phase 1 migration、原 test_models.py、原 P2-A 測試、
API、相依、CI 或原 `P2_B_TEST_EVIDENCE.json`；沒有刪除既有成果。

### 新增測試內容

- 原審查 PlayerWithHand 範例被明確 TypeError 拒絕。
- 帶手牌、repr=False 手牌及其他 secret 欄位的 Player 子類別，在多玩家 tuple 的兩個位置均被拒絕。
- 直接確認惡意範例的 asdict 確實含私有欄位，再確認公開容器拒絕它；不是只靠註記或 repr 判斷。
- 實際逐欄比對合法雙玩家 PublicGameData 的完整 asdict 與 repr，確認沒有 hand、secret、Card 或私密標記。
- 拒絕更新後，原公開物件仍有相同的合法輸出；錯誤文字沒有手牌或私密標記。
- 原始 Player／tuple／Turn 的參照不變，多玩家順序／積分／回合及空集合仍正確。
- 非 Player、dict 外部資料不被隱式轉換成可信 Player。
- Turn 子類別、公開容器子類別，以及略過父類驗證的公開子類別無法進入相應保留邊界。

原 P2-B 124 項與 P2-A 127 項測試檔案保持原內容，均實際重跑通過。

### 實際測試結果與重現

最終證據執行時間：**2026-11-15 19:09:20～19:09:59，UTC+08:00（Asia/Taipei）**。
Windows 11 build 26300、Python 3.12.10、Pytest 9.2.0、Mypy 1.20.2、Ruff 0.17.5。

逐項命令、起訖時間、退出碼、測試數、完整 stdout／stderr、Git 狀態、來源前後 SHA256：
[P2_B_R1_TEST_EVIDENCE.json](P2_B_R1_TEST_EVIDENCE.json)。下表 `PY` 為根目錄
`.\.venv\Scripts\python.exe -B`，執行時設定 PYTHONDONTWRITEBYTECODE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1。

| 實際命令 | 通過 | 失敗 | 略過 | 原始摘要 |
| --- | --- | --- | --- | --- |
| `PY -m pytest backend/tests/games/test_public_isolation.py -q -p no:cacheprovider` | 19 | 0 | 0 | 19 passed in 0.08s |
| `PY -m pytest backend/tests/games/test_models.py -q -p no:cacheprovider` | 124 | 0 | 0 | 124 passed in 1.42s |
| `PY -m pytest backend/tests/games/test_card.py backend/tests/games/test_deck.py -q -p no:cacheprovider` | 127 | 0 | 0 | 127 passed in 0.16s |
| `PY -m pytest backend/tests/test_health.py -q -p no:cacheprovider` | 3 | 0 | 0 | 3 passed, 1 warning in 2.21s |

合計 **273 passed、0 failed、0 skipped**。先前開發檢查也實際執行四個核心檔合併測試，
結果為 `270 passed in 1.85s`，不含三項健康檢查；不把這兩次執行重複加總。

其他最終命令均 exit code 0：

```powershell
.\.venv\Scripts\python.exe -B -m mypy --no-incremental backend/app backend/tests
# Success: no issues found in 22 source files
.\.venv\Scripts\python.exe -B -m ruff check --no-cache backend scripts
# All checks passed!
.\.venv\Scripts\python.exe -B -m ruff format --check --no-cache backend scripts
# 28 files already formatted
.\.venv\Scripts\python.exe -B -m pip check
# No broken requirements found.
```

選定測試不連資料庫、不啟動服務；import 測試只啟動短暫 Python 子程序。
最終命令停用 bytecode／pytest cache／Ruff cache；Mypy 可能更新被忽略的型別快取。
健康檢查仍保留原本的 Starlette／httpx 棄用警告，沒有隱藏或宣告已修復。

### 證據與主要 SHA-256

新證據保存測試前後來源雜湊，並確認執行期間來源不變。原始 P2-B 證據保持逐位元不變，
SHA256 為 `07d214ddf1f6a6a4f034ead576370aa9c51e1d5b44656162f3340191a9528fd8`。
原證據記錄修補前模型，不能要求其舊 models.py 雜湊對上修補後內容，亦不可覆寫成新結果。

| 檔案 | 修補後 SHA-256 |
| --- | --- |
| `backend/app/games/core/models.py` | `3143fcab9378363870d352edf04739c4ecd47bb1346ecc8f1e0a8b7501655800` |
| `backend/tests/games/test_public_isolation.py` | `1687c2c7a4401eb34b787d470f6e0eb05c357180db287051302db66918ead0a9` |
| `backend/tests/games/test_models.py`（未修改） | `ff1cbaeb1da5a927c36d50432a70c0a9188aafbfac9786d155382952b7c8f8e4` |
| `card.py`（未修改） | `1c23d6e028638833a7d06fff4a152b621ab72e68733904aa586a535bbbb8b67b` |
| `deck.py`（未修改） | `c40a1cb60dfe909f7a6e0403fcedb025137b78fae2706776ca096f837c1d4c56` |
| Phase 1 migration（未修改） | `b8e742362dc6a8852c9b6231483817876900a1e46cceb8c3e67bc327a599d2fb` |

### 【推論】仍未解決的風險

- P2-A 四項問題仍開放：reset 亂數失敗、test-only 正式隔離、任意 Python／frozen 信任限制、
  歷史完整回歸版本追溯缺口。R1 只修補公開模型保留子類別的路徑，不宣稱建立 Python 安全沙箱。
- 已結束卻有回合、進行中空玩家、跨手牌／剩餘牌重複及未知遊戲／動作的規則驗證仍未實作。
- PlayerView 仍只有資料一致性檢查，沒有身分驗證／授權或真正逐人投影；正式玩家視圖未通過安全驗收。
- 仍禁止把 asdict(GameState) 當公開輸出。這次沒有新增 JSON codec、通用資料清理或外部資料可信轉換。
- R1 證據只綁定本次選定測試，不補證先前完整回歸，也不能取代尚不存在的 Git 歷史基準。

### 【無法驗證】本輪未執行

一項 SQLite migration 與五項 PostgreSQL 測試沒有執行，不將其視為通過或「本輪零略過」的涵蓋範圍。
Docker／Nginx／named volume 的 Phase 1 驗收仍未完成；原生 DB 生命週期、前端／Playwright、
認證／WebSocket／正式遊戲引擎、多人負載及正式資安亦未驗證。

本輪完成後停止，等待人工獨立複驗；沒有自行宣告 P2-B 結案，也不開始 P2-C～P2-F。
未執行 commit、push、merge、rebase、PR、Git 身分或 Windows 設定變更。

---

## P2-B 原始交付 — 純型別（修補前歷史；獨立驗收 FAIL）

日期：2026-11-15（Asia/Taipei）。P2-A 維持 **CONDITIONAL PASS**。
本輪 P2-B 實作與必要測試完成，**等待人工驗收，未開始 P2-C～P2-F**。
下方 P2-A 紀錄保留為歷史，不代表其中的開放風險已解決。

### 【確認】核對與最小方案

- 讀取七份根目錄規格、TASKS、PHASE_1、原 PHASE_2、既有核心、資料庫目錄模型及相關測試。
- 分支仍是 `feature/phase-1-foundation`；`git rev-parse --verify HEAD` 回傳非零，
  repository 尚無任何 commit，**沒有可解析的 HEAD**。
- 初始 61 份專案檔均未提交；`git status --short --branch` 顯示各根檔／目錄為 untracked。
  以 SHA256 快照保存既有成果，不能用空的 git diff 當成沒有變更。
- 沒有既有 Player／GameState／GameStatus／Turn／GameAction／GameError 可重用；
  SQLAlchemy GameType 僅為遊戲目錄，未將它複製成規則引擎模型。
- 沒有發現阻擋本次授權的規格衝突。舊 P2-03 的 Room／Session／Event／Result 仍未完成，
  以本次明確授權的純型別清單為範圍，不擴充到舊整批工作或後續引擎。
- 原規格提供 UUID、整數積分、玩家座位、版本、request_id、錯誤欄位與隱私原則，
  **沒有逐欄定義共用型別 schema**。本輪採下述最小內部契約，沒有宣稱它是既有 REST／WS 格式。

### 實作契約與邊界

實作位於 `backend/app/games/core/models.py`，沿用 P2-A 的 Enum／frozen dataclass。

| 型別 | 欄位與用途 |
| --- | --- |
| PlayerId | UUID 的 Python 3.12 型別別名；沒有生成 ID 或包裝器執行副作用 |
| Player | id、display_name、seat、points；只含公開資料，id 指使用者身分 |
| GameStatus | waiting／in_progress／finished，最小生命週期，不含遊戲街道或轉移邏輯 |
| Turn | player_id，只描述當前行動者，不選擇下一玩家或啟動計時 |
| GameAction | player_id、request_id、state_version、type，服務端動作中繼資料 |
| GameError | code、message、可選 request_id；純資料，不是 Exception 或 HTTP 回應 |
| PublicGameData | status、state_version、players、turn；沒有手牌、剩餘牌、Deck 或任意 payload |
| PrivatePlayerData | player_id、hand tuple；私有手牌不顯示於 repr |
| PrivateGameData | 私有玩家資料 tuple、remaining_cards tuple；只供後端持有 |
| GameState | session_id、game_type、rules_version、public、private；完整後端內部容器 |
| PlayerView | viewer_id、public、單一 PrivatePlayerData；檢查私有資料 owner 與 viewer 一致 |

驗證必要欄位、UUID、非空文字、真正的非負整數（拒絕 bool／浮點／字串）、Enum 狀態、
不可變 tuple 容器、重複玩家／座位、單一牌集合重複、回合及私有資料的玩家成員關係。
等待中的空玩家集合與空私有資料可合法建立；遊戲特定人數與牌數限制留待規則引擎。

所有建構只檢查資料，不發牌、不洗牌、不產生 UUID、不寫 DB、不做狀態轉移。
GameAction 的 type 可擴充；合法動作、下注／出牌 payload 與合法輪次由後續遊戲實作決定。
PlayerView 的檢查只是資料一致性，**不是認證／授權或 get_player_view 投影實作**。

本輪沒有新增 JSON codec。API_SPEC 仍是待實作的巢狀 action／player_view envelope；
沒有把內部 dataclass 結構直接當成傳輸規格。GameStatus 的值可用 Enum 原生方式往返，已測試。
公開欄位白名單與 `asdict(PublicGameData)` 不含私有欄位，已測試；
**不得序列化整個 GameState 給玩家**，repr=False 也不會使 asdict 自動移除私有欄位。

### 修改／新增檔案

新增：

- `backend/app/games/core/models.py`
- `backend/tests/games/test_models.py`
- `docs/reports/P2_B_TEST_EVIDENCE.json`

修改：

- `backend/app/games/core/__init__.py`：匯出新純資料型別。
- `backend/app/games/README.md`：記錄內部契約與安全限制。
- `TASKS.md`：更新本輪授權／進度，舊 P2-03 未整批勾選。
- `docs/reports/PHASE_2.md`：本報告，保留 P2-A 歷史。

`card.py`、`deck.py`、Phase 1 migration、既有測試、API、相依與 CI 均未修改，沒有刪除成果。

### 實際測試與證據

正式記錄時間：**2026-11-15 17:29:39～17:29:59，UTC+08:00（Asia/Taipei）**。
環境：Windows 11 build 26300、Python 3.12.10、Pytest 9.2.0、Mypy 1.20.2、Ruff 0.17.5。
逐項命令、起訖時間、耗時、exit code、原始 stdout／stderr、Git 分支／無 HEAD、工作區狀態、
測試前後來源 SHA256 全部保存在 [P2_B_TEST_EVIDENCE.json](P2_B_TEST_EVIDENCE.json)。

下表的 `PY` 表示 repository 根目錄的 `.\.venv\Scripts\python.exe -B`。

| 實際命令 | 通過 | 失敗 | 略過 | 原始摘要 |
| --- | --- | --- | --- | --- |
| `PY -m pytest backend/tests/games/test_models.py -q -p no:cacheprovider` | 124 | 0 | 0 | 124 passed in 1.48s |
| `PY -m pytest backend/tests/games/test_card.py backend/tests/games/test_deck.py -q -p no:cacheprovider` | 127 | 0 | 0 | 127 passed in 0.16s |
| `PY -m pytest backend/tests/test_health.py -q -p no:cacheprovider` | 3 | 0 | 0 | 3 passed, 1 warning in 0.82s |

選定的三組測試合計 **254 passed、0 failed、0 skipped**。
這不是整套含資料庫測試的回歸；一項 SQLite migration 與五項 PostgreSQL 測試本輪未選取、未執行。
沒有藉由修改或略過失敗測試使結果通過。

其他實際執行命令與結果：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\.venv\Scripts\python.exe -B -m mypy --no-incremental backend/app backend/tests
# Success: no issues found in 21 source files
.\.venv\Scripts\python.exe -B -m ruff check --no-cache backend scripts
# All checks passed!
.\.venv\Scripts\python.exe -B -m ruff format --check --no-cache backend scripts
# 27 files already formatted
.\.venv\Scripts\python.exe -B -m pip check
# No broken requirements found.
```

測試涵蓋合法建構、必要欄位／None／非法值、Enum 值往返、公開欄位白名單、錯誤層級資料拒絕、
其他玩家私有資料不能放進該 viewer、私有牌面 repr 隱藏、唯讀欄位與 replace 重新驗證、
建構不呼叫牌組／ID 生成，以及六種獨立程序 import 順序無循環依賴、無框架載入。

最初 Ruff 要求把 TypeAlias 註記改成 Python 3.12 的 `type PlayerId = UUID`；修正後完整重跑。
健康檢查仍有原來的 Starlette／httpx 棄用警告，未隱藏。

**副作用範圍**：選定測試不連資料庫、不寫 migration／DB 資料、不啟動服務；
import 測試只建立短暫 Python 子程序。最終檢查停用 bytecode／pytest cache／Ruff cache，
Mypy 檢查可能更新被忽略的型別快取；本輪刻意新增測試證據 JSON 與文件。
未執行原生 PostgreSQL 生命週期腳本，也未安裝任何套件或工具。

### 主要檔案 SHA-256

| 檔案 | SHA-256 |
| --- | --- |
| `backend/app/games/core/models.py` | `d821dd11e87dd3cb58298d27f27140ce4f0aeb50dbb2a8ae7de3243faca3019f` |
| `backend/app/games/core/__init__.py` | `457e03b510cc601271c8eef969ee6f609d3bdca9e9399c857aa8a3bf0be083f6` |
| `backend/tests/games/test_models.py` | `ff1cbaeb1da5a927c36d50432a70c0a9188aafbfac9786d155382952b7c8f8e4` |
| `backend/app/games/core/card.py`（保持原內容） | `1c23d6e028638833a7d06fff4a152b621ab72e68733904aa586a535bbbb8b67b` |
| `backend/app/games/core/deck.py`（保持原內容） | `c40a1cb60dfe909f7a6e0403fcedb025137b78fae2706776ca096f837c1d4c56` |
| Phase 1 `0001_game_types.py`（保持原內容） | `b8e742362dc6a8852c9b6231483817876900a1e46cceb8c3e67bc327a599d2fb` |

來源在本輪正式證據檢查前後雜湊一致。此證據綁定的是本輪選定檢查，
不是先前 136 項完整回歸的版本追溯補證，也不提供 Git 尚不存在的歷史提交基準。

### 【推論】風險及持續開放事項

以下 P2-A 項目全部保留，**P2-B 沒有解決它們**：

1. reset() 安全亂數失敗後，牌組仍可繼續發出固定順序牌的風險。
2. test-only 標記可被同程序程式改寫；正式引擎隔離尚未實作。
3. Python frozen dataclass 與子類別／任意 Python 程式碼的信任限制；新模型也不是安全沙箱。
4. 先前完整回歸證據的程式版本追溯缺口。

此外，新型別只驗證結構，尚未提供：跨牌集合守恆、遊戲合法人數／動作／狀態轉移、
真實身分綁定、私有資料投影、未知 game_type／錯誤 code 的 registry 驗證或 JSON schema。
GameError 的 message 須由呼叫端確保可公開，不會自動清除任意字串中的機密資訊。
這些都不應由建立資料物件時偷偷執行。

### 【無法驗證】本輪未執行

- SQLite／PostgreSQL migration、真實 DB 交易及 API 重連；本輪沒有修改相關功能。
- Phase 1 P1-08／P1-08d：Docker Engine 不存在，容器／Nginx／named volume 實際驗收仍未完成。
- Docker／WSL／Windows 設定操作、GitHub CI、前端型別／建置／Playwright、真實裝置或多人負載。
- 正式發牌、引擎／Registry、認證授權、下注結算、安全稽核與備份恢復。

本輪到此停止。未開始 P2-C～P2-F，未接入正式發牌，未執行 commit、push、merge、rebase、PR
或 Git 身分變更。下一階段須等待人工驗收與另行授權。

---

## P2-A 歷史交付紀錄（原文；驗收狀態以目前 CONDITIONAL PASS 為準）

日期：2026-11-15（Asia/Taipei）。本輪只授權 Card／Deck／安全洗牌。
狀態：**P2-A 實作與本機測試完成，等待人工驗收**；整個 Phase 2 尚未完成。
未開始 P2-B～P2-F，未建立可執行遊戲、引擎 Protocol 或 Registry。

## 【確認】唯讀盤點

- `git status --short --branch`：`No commits yet on feature/phase-1-foundation`。
- `git branch --show-current`：`feature/phase-1-foundation`。
- `git rev-parse --verify HEAD`：`fatal: Needed a single revision`，原因是 repository 尚無任何 commit，
  不是遺失既有提交。未切換分支或修改 Git 狀態。
- `git diff --stat`、`git diff --cached --stat` 均無內容；所有 54 份既有專案檔都是 untracked，
  因此不能只用 git diff 判斷是否保留先前成果。
- 已閱讀 README、PRD、GAME_RULES、API_SPEC、DATABASE、SECURITY、TASKS、PHASE_1 報告，
  以及相關 games 邊界、後端模型／API、既有測試、Pytest／Mypy／Ruff 設定與原生驗收腳本。
  repository 與上層目錄未找到 AGENTS.md。
- 未找到 Card／Deck／Shuffle／遊戲型別的既有實作。GameType 是資料庫目錄模型，
  不是遊戲狀態型別。六方法介面與 Registry 只有規劃。
- 六方法既有規格為 create_game、validate_action、apply_action、get_player_view、
  is_game_over、calculate_result；仍僅保留規格，未新增 stub。
- 沒有發現阻擋 P2-A 的工作區衝突或規格矛盾。TASKS 原本「等待 Phase 2 確認」的限制，
  由本次使用者的「僅授權 P2-A」更新；其餘限制保留。

修改前使用既有原生 PostgreSQL 腳本重跑 Phase 1：**9 passed、0 skipped**，
同時確認真實 HTTP 與 DB 停止／重啟後 API 重連通過。
該次證據：`.local-data/p1-native-c42de7397fff/result.json`。

## 實作功能及契約

### Card

- 不可變、可雜湊的 frozen dataclass；Rank 與 Suit 為 Enum。
- 四種花色 C／D／H／S，十三種點數 2～10／J／Q／K／A，沒有 Joker。
- 建構時只接受對應 Enum 成員，拒絕字串、整數、bool 等隱式轉型。
- `card.code` 與 `Card.from_code()` 往返，例如 AS、10H；只接受大寫、無空白的明確牌面碼。
- 不定義 Card 大小比較，Enum 宣告順序也不代表各遊戲的勝負或花色優先序。
  大老二花色及順子規則仍留在未來設定模組，不在共用模型內實作。

### Deck、安全洗牌與測試注入

- `Deck()` 建立標準 52 張不重複牌並立即以 `secrets.SystemRandom` 洗牌。
- `deal(count=1)` 從牌序前端取牌，回傳 tuple；`remaining_count` 提供剩餘數量。
- count=0 合法；負數拒絕；bool、浮點、字串、None 等非整數拒絕。
- 超額發牌拋出 InsufficientCardsError，驗證先於狀態修改，失敗不丟牌或改變順序。
- `shuffle()` 只洗剩餘牌，不放回已發牌；`reset()` 恢復完整牌組並重新安全洗牌。
- 固定測試牌序只由 `Deck.for_testing(cards)` 注入；允許部分／空牌組，複製輸入、
  拒絕非法元素與重複牌，reset 後重現原指定順序。
- 測試工廠建立的 `is_test_only=True` 標記在 shuffle／reset 後仍保留，公開屬性不可改。
  正式建構子沒有 seed、rng、cards 或關閉洗牌參數；相應拒絕行為已測試。
- repr 只顯示剩餘數及測試標記；沒有牌序日誌或任何 API／前端暴露。
- 僅使用 Python 標準函式庫，未新增套件或更新 lock，核心不依賴 FastAPI／SQLAlchemy／瀏覽器。

使用例：

```python
from app.games.core import Card, Deck

deck = Deck()                     # 標準 52 張，已安全洗牌
hand = deck.deal(2)               # tuple[Card, ...]
assert deck.remaining_count == 50
deck.reset()                     # 52 張，重新安全洗牌

fixture = Deck.for_testing([Card.from_code("AS"), Card.from_code("10H")])
assert fixture.is_test_only
assert fixture.deal()[0].code == "AS"
```

固定牌序工廠是受信任 Python 測試程式的入口，不是前端可傳入的設定。
未來引擎接入時必須拒絕 test-only 牌組；該接入防護屬 P2-C／後續整合，不在本輪提前實作。

## 修改及新增檔案

新增：

- `backend/app/games/__init__.py`
- `backend/app/games/core/__init__.py`
- `backend/app/games/core/card.py`
- `backend/app/games/core/deck.py`
- `backend/tests/games/test_card.py`
- `backend/tests/games/test_deck.py`
- `docs/reports/PHASE_2.md`

修改：`TASKS.md`、`backend/app/games/README.md`，只更新本輪進度、契約及後續規劃。

以修改前 54 份既有檔案 SHA256 快照比對，除上述兩份文件外，其餘既有檔案內容不變，
沒有刪除檔案。Phase 1 migration、API、既有測試、驗收腳本及相依設定均保持原內容。
初始 migration SHA256 前後一致：
`b8e742362dc6a8852c9b6231483817876900a1e46cceb8c3e67bc327a599d2fb`。

## 實際測試命令與結果

工作目錄為 `D:\github\Poker-Club`，Python 3.12.10，沿用既有 .venv 與免安裝 PostgreSQL 17.12。

| 實際命令 | 最終結果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/games -q` | **127 passed in 0.22s** |
| `.\.venv\Scripts\python.exe scripts/verify_phase1_native_postgres.py --pg-bin .local-tools/pgsql/bin`（修改前） | **9 passed, 1 warning in 3.49s**；原生 DB／HTTP 重啟流程通過 |
| 同一原生驗收命令（修改後） | **136 passed, 1 warning in 3.67s**；0 skipped；DB／HTTP 重啟流程通過 |
| `.\.venv\Scripts\python.exe -m mypy backend/app backend/tests` | Success: no issues found in **19 source files** |
| `.\.venv\Scripts\python.exe -m ruff check backend scripts` | All checks passed! |
| `.\.venv\Scripts\python.exe -m ruff format --check backend scripts` | **25 files already formatted** |
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements found. |

完整回歸的 Pytest 命令由未修改的既有原生驗收腳本執行：
`python -m pytest backend/tests -q`，腳本自行設定 TEST_DATABASE_URL 到其新建拋棄式 DB。
這次並未依賴未設定資料庫而跳過五項 PostgreSQL 測試。

修改後實際證據：`.local-data/p1-native-e41d28d0c993/result.json`，內容摘要：

```json
{
  "scope": "native PostgreSQL only; Docker/Nginx not validated",
  "passed": true,
  "checks": [
    "pytest passed without skips",
    "real HTTP: live=200, ready=200",
    "database stopped: live=200, ready=503 without secret details",
    "database restart: marker persisted, API recovered to ready=200"
  ]
}
```

也在獨立 Python 程序執行核心 import 與建立牌組：`core_import_ok=True`，
`frameworks_loaded=[]`（未載入 fastapi、sqlalchemy、pydantic）。

測試涵蓋 52 種牌面往返、所有合法花色／點數、非法牌面／非字串／錯誤 Enum、不可變性、
52 張唯一性、洗牌守恆、逐張不重複發牌、剩餘數、原子拒絕超額／負數／非整數、
空牌組／零張邊界、固定序列重現、輸入複製、reset、測試標記與安全建構子拒絕項目。
安全亂數測試觀察真正 SystemRandom 的使用，不以「洗完一定不同」等機率斷言判定成敗。

初次檢查發現測試的唯讀欄位修改／不支援排序操作需要刻意繞過靜態型別檢查，
以及 Ruff B010／B015／格式問題；已修正測試寫法後重跑。
沒有刪除原測試、放寬既有驗證、隱藏警告或跳過失敗項目。
Starlette TestClient 的 httpx 棄用警告仍為原有 **1 warning**。

## 【推論】已知限制與人工決策

- 固定牌序的測試標記用於避免誤用，不是任意 Python 程式碼的安全沙箱；未來正式引擎
  仍須建立入口限制，禁止客戶端提供牌組／牌序，且不得接受 test-only 實例。
- Deck 是每場後端獨立持有的可變物件，不保證跨執行緒共用安全；多人交易與事件同步尚未實作。
- 亂數來源採 OS 支援的 SystemRandom；本輪驗證來源與牌組守恆，不宣稱已做密碼學稽核或統計驗證。
- 未實作持久化、初始牌序保護／重播、遊戲型別、六方法引擎、Registry、牌型或任何遊戲。
- P2-A 沒有阻擋交付的人工決策。人工驗收可確認目前牌面碼、reset／deal 語意及測試工廠契約；
  此牌面碼尚未成為 REST／WS 或資料庫欄位的既有外部契約。
- P2-B～P2-F 的名稱及舊 P2-03～07 對照是建議規劃，開始下一批前仍需使用者確認。

## 【無法驗證】保留限制

- Phase 1 的 **P1-08／P1-08d 仍未完成**：Docker Engine 不存在；容器 build/up、Nginx 實際代理、
  容器健康、named volume 及容器重啟持久性尚未驗證。先前 Compose 解析成功不代表容器通過。
- 本輪沒有執行 Docker／WSL／Windows 設定操作，也未觸發 GitHub CI。
- TypeScript、前端 lint/build、Playwright 與瀏覽器裝置測試本輪未執行：本次僅新增純 Python 核心，
  沒有 UI、前端契約或 HTTP 路由變更；不把 Phase 1 的前端結果宣稱為本輪重跑結果。
- 多人負載、斷線玩家恢復、隱藏牌授權、下注結算、備份／恢復及正式環境資安尚無法以本輪核心驗收。

## P2-B 至 P2-F 建議順序（僅規劃）

1. **P2-B**：Player／Room／GameSession／GameEvent／GameResult 純型別、版本與錯誤語意，
   先決定哪些欄位可公開、哪些只屬後端。
2. **P2-C**：六方法 GameEngine Protocol，固定輸入輸出／合法動作／玩家視圖契約，
   納入正式牌組來源及 test-only 拒絕規則。
3. **P2-D**：Registry 與重複／未知代碼錯誤、未實作遊戲不可啟用；不提前建立假引擎。
4. **P2-E**：純牌型辨識／比較測試，涵蓋 wheel、踢腳、同牌型平手；仍不實作下注狀態機。
5. **P2-F**：私有資訊投影、十三支擴充契約及整個 Phase 2 的整合驗收／報告。

本輪在 P2-A 完成後停止。沒有 commit、push、merge、rebase、PR 或 Git 身分變更。
若日後授權提交，可參考訊息 `feat: add secure card and deck primitives`；目前未執行提交。
