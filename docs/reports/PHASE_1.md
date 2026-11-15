# Phase 1 階段報告

日期：2026-11-15（Asia/Taipei）。僅交付 Phase 1，未開始 Phase 2。
目前狀態：**程式初始化完成，基礎環境部分驗收**。
原生 PostgreSQL 補驗通過；**Docker 容器與 Nginx 實際執行驗收仍未完成**。

## 本輪補驗結論（取代下方初次交付的環境狀態）

依使用者最新指示：不安裝 Docker Desktop、不啟用 WSL、不改 Windows 系統設定。
不開始 Phase 2、不 commit/push/merge、不修改 Git 身分。
下方「初次交付紀錄」保留當時的 4 passed／1 skipped，不能當作本輪最新結果。

### 【確認】本輪通過

1. 重新檢查 Git 仍為 `feature/phase-1-foundation`、無任何 commit，所有專案檔案仍未提交。
2. 本機未找到 Docker CLI／Desktop／daemon，WSL 回報尚未安裝；未修改這些系統功能。
3. 從 PostgreSQL 官方 Windows 頁連結之 EDB 下載 PostgreSQL **17.12** binaries，
   僅解壓到被 Git 忽略的 `.local-tools/pgsql`，不安裝服務、不改 PATH。
4. 官方 Docker Compose standalone **v5.7.1** 下載至 `.local-tools`，與同一官方 release
   的 checksums.txt 比對 SHA256 一致，再執行設定解析。
   SHA256：`e4316597452650ae92fe9719a2a7c2fce8f56c5ceafed88d2aed6e39b2b2b2d0`。
5. 新增真實 PostgreSQL 測試：UUID 原生型別、中文目錄、UTC 時間、停用旗標、唯一及
   人數 CHECK 約束、交易回滾、真實資料庫 readiness 與過期 migration 拒絕。
6. 修正測試資料隔離：每項測試建立全新 `poker_test_<uuid>` schema，結束時只清理自身
   schema，避免原本重跑時資料庫非空而失敗。migration 仍執行 upgrade/downgrade/upgrade。
7. 全套 Pytest **9 passed、0 skipped**；另單獨重跑 PostgreSQL 測試 **5 passed、4 deselected**。
8. 原生 PostgreSQL 停止前 readiness=200；停止後 API 仍存活且 readiness=503；
   重啟後先前寫入的 UUID 標記仍存在，**同一 API process 自動恢復 readiness=200**。
9. 新增原生／Docker 驗收腳本與 Docker CI job。原生腳本實測成功；Docker 腳本只跑到
   設定解析與 engine 阻擋，後面的容器操作及 GitHub CI 尚未執行。

### 實際命令與輸出

本輪使用 PowerShell；環境仍為 Windows／Python 3.12.10。測試密碼隨機產生，
只保存於被忽略的 `.local-data`，不寫入本報告、Git 或 Docker build context。

```powershell
.\.local-tools\pgsql\bin\postgres.exe --version
# postgres (PostgreSQL) 17.12

.\.local-tools\docker-compose.exe version
# Docker Compose version v5.7.1

.\.local-tools\docker-compose.exe --env-file .local-data/compose-acceptance.env config --quiet
# 無輸出，exit code 0：僅 Compose 設定解析成功。

.\.venv\Scripts\python.exe -m pytest backend/tests -q
# 本輪已設定 TEST_DATABASE_URL 指向本輪獨立 PostgreSQL：
# 9 passed, 1 warning in 7.32s

.\.venv\Scripts\python.exe -m pytest backend/tests -m postgres -q
# 使用同一測試資料庫重跑，無殘留 schema 阻擋：
# 5 passed, 4 deselected, 1 warning in 3.11s

.\.venv\Scripts\python.exe scripts/verify_phase1_native_postgres.py --pg-bin .local-tools/pgsql/bin
# postgres (PostgreSQL) 17.12
# 9 passed, 1 warning in 3.75s
```

最後一個腳本自行建立全新 cluster、測試資料庫、隨機埠、密碼，再執行 Pytest、migration、
啟動真實 Uvicorn HTTP server、停止／啟動 PostgreSQL，檢查 UUID 標記與 HTTP 回應。
成功的實際結果為：

```json
{
  "scope": "native PostgreSQL only; Docker/Nginx not validated",
  "passed": true,
  "checks": [
    "pytest passed without skips",
    "real HTTP: live=200, ready=200",
    "database stopped: live=200, ready=503 without secret details",
    "database restart: marker persisted, API recovered to ready=200"
  ],
  "data_directory": ".local-data\\p1-native-9fde7f501f5d"
}
```

證據檔：`.local-data/p1-native-9fde7f501f5d/result.json`；同目錄保留 PostgreSQL 資料、
postgres.log、api.log 與測試密碼檔，均不提交。腳本成功結束前已停止其啟動的 API／DB。
最初手動建立的測試 cluster 亦已停止。

```powershell
.\.venv\Scripts\python.exe -m ruff check backend scripts
# All checks passed!
.\.venv\Scripts\python.exe -m ruff format --check backend scripts
# 19 files already formatted
.\.venv\Scripts\python.exe -m mypy backend/app backend/tests scripts/verify_phase1_docker.py scripts/verify_phase1_native_postgres.py
# Success: no issues found in 15 source files
.\.venv\Scripts\python.exe -m pip check
# No broken requirements found.

.\.venv\Scripts\python.exe scripts/verify_phase1_docker.py --compose .local-tools/docker-compose.exe
# PASS: Compose configuration
# FAIL/BLOCKED: failed to connect to the docker API at npipe:////./pipe/docker_engine;
# check if the path is correct and if the daemon is running:
# open //./pipe/docker_engine: The system cannot find the file specified.
# exit code 1；沒有啟動或建置任何容器。
```

Starlette TestClient 的 httpx 棄用警告仍存在，未隱藏或宣稱已修復。
前端本輪未變更，沿用初次交付已通過的型別／lint／build／Playwright 結果，沒有宣稱本輪重跑。

### 未通過、修正與無法執行

- **尚未通過**：完整 Phase 1 基礎環境驗收。Docker 腳本因 engine 不存在失敗，
  Compose 解析成功不是容器驗收成功。
- **已修正的工具問題**：首次 checksum 比對未處理官方清單中的 `*filename` 格式而拒絕執行，
  修正解析後雜湊一致才執行 Compose；不是忽略雜湊不符。
- **已修正的腳本問題**：最初相對 Compose 路徑在 Windows subprocess 找不到，改為絕對路徑。
- **已修正的型別問題**：原生腳本 psycopg 連線參數字典型別不符，改用 conninfo，Mypy 通過。
- **首次原生重啟腳本未通過**：Windows 背景子程序／pipe 生命週期造成啟動等待問題，
  該次測試被中止並保留 `p1-native-03e71dc27fc0/result.json` 的 `passed:false`。
  改用檔案擷取子程序輸出後，在全新 cluster 重跑，上列 `9fde7f501f5d` 結果為 true。
- **無法執行**：Docker build/up、容器內 nginx -t、Nginx 實際代理、容器健康檢查、
  PostgreSQL named volume、容器重啟／重建持久性；GitHub Actions 也未觸發。
- **不在本次驗收範圍**：備份／恢復、多人負載、WS、跨瀏覽器與正式部署資安。

### 本輪修改檔案與重現

新增：`backend/tests/conftest.py`、`backend/tests/test_postgres_foundation.py`、
`scripts/verify_phase1_docker.py`、`scripts/verify_phase1_native_postgres.py`。

修改：`backend/tests/test_migrations.py`、`compose.yaml`（DB_PORT 可設定，以隔離驗收埠）、
`.env.example`、`.gitignore`、`.dockerignore`、`.github/workflows/ci.yml`（待執行的容器驗收 job）、
`README.md`、`DATABASE.md`、`TASKS.md`、本報告。

重現 PostgreSQL 全流程：先依 README 安裝鎖版 backend dev 相依，從 PostgreSQL 官方網站
連結的 EDB binaries 解壓到 `.local-tools`，再執行上述 native 腳本即可。
它不需要先啟動既有資料庫，不會碰觸既有 cluster，也不安裝任何 Windows 服務。
若只測外部拋棄式 PostgreSQL，設定 TEST_DATABASE_URL 後執行 Pytest；帳號須能建立 schema。

官方工具來源：[PostgreSQL Windows](https://www.postgresql.org/download/windows/)、
[EDB binaries](https://www.enterprisedb.com/download-postgresql-binaries)、
[Docker Compose standalone](https://docs.docker.com/compose/install/standalone)、
[Compose v5.7.1 release](https://github.com/docker/compose/releases/tag/v5.7.1)。

本輪到此停止，等待使用者確認；沒有開始 Phase 2，沒有執行 commit、push、merge 或 Git 身分變更。

---

## 初次交付紀錄（歷史，非最新環境驗收狀態）

## 【確認】實際完成

- 首次檢查工作目錄為空，無 .git 或現有程式；`git ls-remote` 成功但未回傳 refs。
- 初始化 Git 並切至 `feature/phase-1-foundation`，origin 為使用者指定 URL。
  main 未寫入提交，目前為尚無任何 commit 的 repository；未改 Git 身分、未 commit/push/merge。
- 七份指定文件、可獨立驗收的 P1～P7 任務與規則／安全邊界。
- React、TypeScript、Vite、Tailwind CSS、Framer Motion 基礎網站與繁中桌面／手機布局。
  頁面明示開發階段，唯一動作按鈕實際呼叫後端 API；視覺牌桌明示為示意。
- FastAPI 存活與資料庫 readiness；故障回應不洩漏底層 SQL 或連線憑證。
- SQLAlchemy 2 Base、Session、GameType model 與 Alembic 初始 migration。
  僅建立 game_types 與版本表，四筆停用目錄是遊戲規格，不是多人或牌局假資料。
- Docker Compose 的 PostgreSQL、一次性 migration、單 worker API、Nginx 設定、named volume。
  PostgreSQL 與網站皆只綁定本機，沒有自動對外公開。
- Pytest、Ruff、Mypy、ESLint、TS 與 Playwright 基本環境，Python／npm lock。
- GitHub Actions 工作流程包含 PostgreSQL service 與檢查；已寫好，未在 GitHub 執行。

環境：Windows PowerShell、Python 3.12.10、Node.js 26.13.1、npm 11.20.0。
PowerShell 禁止 npm.ps1，使用 npm.cmd，未改 execution policy。
未找到 Docker、psql、pg_isready；未安裝或聲稱啟動 PostgreSQL。

## 實際執行命令與結果

以下除註明外均在 repository 根目錄執行，採最後一次執行結果：

| 命令 | 結果 |
| --- | --- |
| `python -m venv .venv` | 成功建立本機虛擬環境 |
| `.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'` | 成功安裝 |
| `.\.venv\Scripts\python.exe scripts/lock_requirements.py` | 成功產生 runtime/dev lock |
| `.\.venv\Scripts\python.exe -m pytest backend/tests -q` | **4 passed, 1 skipped**；1 個相依套件棄用警告 |
| `.\.venv\Scripts\python.exe -m ruff check backend scripts` | 通過 |
| `.\.venv\Scripts\python.exe -m ruff format --check backend scripts` | 15 個 Python 檔案格式正確 |
| `.\.venv\Scripts\python.exe -m mypy backend/app backend/tests` | 11 個來源檔無型別錯誤 |
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements found |
| `.\.venv\Scripts\python.exe -m pip install --dry-run -r backend/requirements-dev.lock` | 鎖版相依均已滿足；不是乾淨環境重裝測試 |
| `npm.cmd --prefix frontend install` | 成功，產生並更新 package-lock.json |
| `npm.cmd --prefix frontend run typecheck` | 通過 |
| `npm.cmd --prefix frontend run lint` | 通過，零 lint 警告 |
| `npm.cmd --prefix frontend run build` | 通過，Vite 8.3.8 正式建置輸出 |
| `npm.cmd --prefix frontend exec -- playwright install chromium` | 成功安裝 Chromium 測試引擎 |
| `npm.cmd --prefix frontend run test:e2e` | **4 passed (8.6s)** |
| `npm.cmd --prefix frontend audit` | **0 vulnerabilities**，僅表示該次 npm 公告資料庫檢查 |
| `..\.venv\Scripts\python.exe -m alembic upgrade head --sql`（backend 目錄） | 成功產生 PostgreSQL DDL 與 catalog INSERT，未連線資料庫 |
| PyYAML `safe_load` 解析 compose.yaml 與 ci.yml | 通過 YAML 語法解析；不是 Compose/Nginx 語意或執行驗證 |

Pytest 驗證：存活不依賴 DB、readiness 故障不洩漏敏感資訊、舊版 schema 被拒絕，
以及 SQLite migration upgrade/downgrade/upgrade 與 ORM metadata 一致性。
PostgreSQL 測試因未設 TEST_DATABASE_URL 而 skip。

Playwright：桌面 Chromium 1280×720、Pixel 7 模擬視窗 393×727，各執行兩項測試。
驗證繁中首頁、開發狀態標示、無水平溢出、真實 FastAPI HTTP 連線、網路失敗與重試。
人工檢視兩個 full-page 截圖；測試未使用多人假資料，也未驗證多人遊戲。
測試截圖／失敗 trace 在被 Git 忽略的 frontend/test-results，重跑會重新產生。

## 檢查過程與已知警告

- 第一次 Pytest 啟動時 pip 尚在安裝，發生 import collection error；等待安裝完成後重跑通過。
- 第一次 E2E 2 passed / 2 failed，原因為 heading 的換行空白與精確文字 locator 不符；
  改用 level=1 與允許空白的文字斷言，重跑 4 passed，仍檢查完整標題。
- 初次 npm audit 發現 7 個中度項目，同源於開發工具的 minimatch DoS。
  一般 audit fix 未修復；更新 ESLint／Vite 工具及 scoped minimatch 11.0.1+ override 後為 0，
  並重跑型別／lint／build／E2E。沒有用 force 升級或忽略 audit。
- Starlette TestClient 仍提示 httpx 將棄用、建議 httpx2；目前相依已鎖版、測試可執行。
  後續更新時需驗證新版測試客戶端 API，未隱藏警告。
- 直接執行 alembic.exe 被本機拒絕存取；改以同一 venv 的 `python -m alembic`
  成功執行 PostgreSQL offline SQL 產生，README 已採此可重現命令，未調整系統安全政策。
- Playwright 伺服器有 NO_COLOR / FORCE_COLOR 環境提示，不影響測試結果。

## 修改檔案清單（全部新增，未提交）

```text
.dockerignore
.env.example
.github/workflows/ci.yml
.gitignore
README.md
PRD.md
GAME_RULES.md
API_SPEC.md
DATABASE.md
SECURITY.md
TASKS.md
compose.yaml
backend/.dockerignore
backend/Dockerfile
backend/pyproject.toml
backend/requirements.lock
backend/requirements-dev.lock
backend/alembic.ini
backend/app/__init__.py
backend/app/main.py
backend/app/container_entrypoint.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/models.py
backend/app/db/session.py
backend/app/games/README.md
backend/migrations/env.py
backend/migrations/script.py.mako
backend/migrations/versions/0001_game_types.py
backend/tests/test_health.py
backend/tests/test_migrations.py
frontend/.dockerignore
frontend/package.json
frontend/package-lock.json
frontend/index.html
frontend/tsconfig.json
frontend/vite.config.ts
frontend/eslint.config.js
frontend/playwright.config.ts
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/styles.css
frontend/e2e/foundation.spec.ts
infra/web.Dockerfile
infra/nginx/default.conf
infra/nginx/upgrade.conf
scripts/lock_requirements.py
docs/reports/PHASE_1.md
```

## 可重現方式

依 README 本機安裝章節，用 Python 3.12 建 venv、安裝 requirements-dev.lock、
以 --no-deps 安裝 backend editable，再執行 npm ci 與 Chromium install。
逐一執行上表檢查命令。E2E 會自行啟動並停止 8000 與 5173 的伺服器，請先保持兩埠空閒。
不需要資料庫即可重現 4 個單元／migration smoke 測試與 4 個 E2E。
要補 PostgreSQL 驗證，依 README 建立空的拋棄式資料庫並設定 TEST_DATABASE_URL。
要補容器驗證，編輯 .env 後執行 docker compose config、up --build、ps 與兩個 health URL。

## 【推論】未完成與風險

- 遊戲引擎、認證、房間、WS、下注、結算、其他八表 migration 與歷史尚未實作，屬後續範圍。
- PostgreSQL 是部署目標，目前只有容器設定；實際連線、TIMESTAMPTZ、資料持久性仍待驗證。
- HTTP 與單 worker 是初始化設定；公開部署前需 TLS、認證與完整資安檢查。
- Windows 產生的 Python pins 與 Linux 容器套件安裝尚未跨平台驗證；Docker images 也尚未拉取。
- minimatch override 跨 major，現有 lint／build／E2E 通過，但更新 typescript-eslint 後應移除或重新驗證。
- 不可將現有健康檢查或單頁 E2E 當作多人平台或正式環境驗收。

## 【無法驗證】本輪未執行

- Docker build/up、Compose 語意驗證、Nginx 設定測試與實際反向代理／健康啟動依賴。
- PostgreSQL migration 往返、交易隔離、競態、重啟後 volume 持久性。
- GitHub Actions 遠端執行與 Linux／Node.js 22 環境。
- Firefox、WebKit、Safari、實際 Android／iOS 裝置。
- 多人負載、延遲、WS 重連、隱藏牌越權、完整滲透與後端依賴弱點掃描。
- 備份／恢復、事件重播、正式環境安全與部署驗收。

## Phase 2 實作計畫（未開始）

1. 建立 Card／Rank／Suit 與 52 張 Deck，驗證唯一性、序列化與非法牌。
2. 以安全亂數洗牌，測試可注入固定牌序、抽牌順序、耗盡與牌數守恆。
3. 建立 Player／Room／GameSession／GameEvent／GameResult 純型別，定義版本與動作錯誤。
4. 建立六方法 GameEngine Protocol 與 registry，驗證未知／重複註冊及型別契約。
5. 建立五張牌型純函式與比較測試：所有牌型、A2345、踢腳、平手、輸入錯誤。
   先不實作德州下注狀態機與大老二規則，留在 Phase 3／4。
6. 定義私有資訊投影契約與十三支可擴充介面，不啟用未實作引擎。
7. 執行核心 Pytest、Mypy、Ruff，更新 TASKS 與 Phase 2 報告，再停止交付。

各項獨立驗收見 TASKS 的 P2-01～P2-07。P1-08 在具備 Docker／PostgreSQL 環境後另補。

建議 commit：`chore: initialize Poker Club phase 1 foundation`。
尚未執行 commit；依使用者規則，等待明確授權後才提交。
本輪在此停止；Phase 2 必須等待使用者確認。
