# Phase 2 進度報告

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
