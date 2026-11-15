# Poker Club

繁體中文瀏覽器多人撲克牌平台，只使用無現金價值的遊戲積分。
目前為 Phase 1：程式初始化完成，基礎環境部分驗收；**不能登入、開房或進行牌局**。
原生 PostgreSQL 測試已通過，Docker Engine 不存在，容器驗收仍未完成。
不提供เงินจริง下注、兌換、支付、交易。

## 架構及目錄

Modular Monolith：React / TypeScript / Vite / Tailwind CSS / Framer Motion → Nginx →
FastAPI → SQLAlchemy 2 / PostgreSQL。Redis 留待分散式階段。

- `frontend/`：繁中基礎頁面、實際 API 存活檢查、Playwright。
- `backend/app/`：設定、健康檢查、資料庫模型；`games/` 保留引擎邊界。
- `backend/migrations/`：Alembic 版本與初始遊戲目錄。
- `infra/nginx/`：靜態網站、API / 未來 WebSocket 反向代理。
- `docs/reports/`：各階段驗證、限制與下一階段計畫。
- 產品、規則、API、資料庫、安全與工作驗收請見根目錄各規格。

## 本機開發（PowerShell）

需求：Python 3.12+、Node.js 22.12+（本次使用 26.13.1）、Docker Compose v2。
本機沒有 Docker 時仍可執行單元測試及前端；資料庫 readiness 會回傳 503。

```powershell
Copy-Item .env.example .env
# 編輯 .env，設定獨立密碼；勿提交 .env。
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e ./backend
npm.cmd --prefix frontend ci
docker compose up -d db
Set-Location backend
# 本機 backend 從此目錄讀取 .env，明確載入根目錄設定：
$env:DATABASE_URL = 'postgresql+psycopg://poker:YOUR_URL_ENCODED_PASSWORD@localhost:5432/poker_club'
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

另開終端：`npm.cmd --prefix frontend run dev`，瀏覽 http://localhost:5173。
API 文件：http://localhost:8000/docs。Linux/macOS 將 `.venv\Scripts` 換成 `.venv/bin`，使用 `npm`。
DATABASE_URL 的使用者名稱、密碼須 URL encode；Compose 會自動編碼環境中的資料庫憑證。

## 容器部署骨架

```powershell
Copy-Item .env.example .env
# 編輯密碼後
docker compose config --quiet
docker compose up --build -d
docker compose ps
curl.exe --fail http://localhost:8080/api/health/live
curl.exe --fail http://localhost:8080/api/health/ready
```

Compose 先等待 PostgreSQL 健康，再由一次性 migrate 服務升級 schema，最後啟動 API 與 Nginx。
資料庫只綁定 localhost；網站預設 http://localhost:8080。
此為單機 HTTP 骨架，公開部署前需完成 TLS、認證與後續安全工作。
`docker compose down` 保留 named volume；不要對需保留的資料執行 `down -v`。

## 可重現驗證（repository 根目錄）

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
.\.venv\Scripts\python.exe -m mypy backend/app backend/tests
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend audit
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend exec -- playwright install chromium
npm.cmd --prefix frontend run test:e2e
```

E2E 自行啟動 Vite 與 Python API，以真實 HTTP 驗證首頁與存活檢查，沒有假多人資料。
預設使用根目錄 `.venv`；可透過 `E2E_PYTHON` 指向其他 Python 執行檔。

PostgreSQL 測試僅可指向**拋棄式測試資料庫**，測試帳號須具備建立 schema 權限。
每項測試建立獨立 `poker_test_<uuid>` schema，migration 往返只操作該 schema，結束後清理，
不會刪除既有 public 資料表：

```powershell
docker compose exec db createdb -U poker poker_club_test
$env:TEST_DATABASE_URL = 'postgresql+psycopg://poker:YOUR_URL_ENCODED_PASSWORD@localhost:5432/poker_club_test'
.\.venv\Scripts\python.exe -m pytest backend/tests -m postgres -q
Remove-Item Env:TEST_DATABASE_URL
```

未設定 TEST_DATABASE_URL 時五項 PostgreSQL 測試明確 skip；SQLite 測試不能替代 PostgreSQL 驗證。
執行紀錄及未驗證項目見 [Phase 1 報告](docs/reports/PHASE_1.md)。

## Phase 1 環境補驗

若已有 PostgreSQL 解壓縮版，可執行以下命令，不需安裝 Windows 服務或修改系統設定：

```powershell
.\.venv\Scripts\python.exe scripts/verify_phase1_native_postgres.py --pg-bin .local-tools/pgsql/bin
```

腳本建立獨立本機 cluster／隨機埠與測試密碼，執行全部 Pytest，透過真實 HTTP 驗證
API 存活／readiness、資料庫停止後 503、重啟後資料保留與 API 重新連線。
結束時停止自身啟動的 API 與 PostgreSQL，保留 `.local-data/p1-native-*/result.json` 及資料供檢視。
`.local-data` 包含測試憑證，已排除 Git 與 Docker build context。
PostgreSQL 解壓縮版來源：[官方 Windows 下載頁](https://www.postgresql.org/download/windows/)
連結的 [EDB binaries](https://www.enterprisedb.com/download-postgresql-binaries)。

未來已有 Docker engine 時，可使用獨立的一次性測試專案驗收：

```powershell
.\.venv\Scripts\python.exe scripts/verify_phase1_docker.py
# 僅有 standalone Compose 時：
.\.venv\Scripts\python.exe scripts/verify_phase1_docker.py --compose .local-tools/docker-compose.exe
```

Docker 腳本規劃驗證 build/up、Nginx、代理／API、PostgreSQL 測試與容器重啟資料保留；
只清理本次隨機專案的容器與 volume，不操作預設專案。**目前因缺 engine，僅設定解析
與阻擋回報已執行，後面的容器驗收流程尚未實測。** 不會自動安裝 Docker 或啟用 WSL。

Python 相依更新後以 `.\.venv\Scripts\python.exe scripts/lock_requirements.py` 重建兩份 lock。
lock 由 Windows / Python 3.12 產生，列出明確套件版本；Linux 使用 Uvicorn 可攜事件迴圈，
不額外解析 uvloop。跨平台容器相依安裝仍須在 Docker 環境驗證。
前端暫將 typescript-estree 的 minimatch 升到 11.0.1+ 修補開發工具 DoS 公告；
更新 typescript-eslint 後需重新檢查是否可移除此 override。

## 後續開發與 Git

每個工作項目及驗收條件見 [TASKS.md](TASKS.md)。Phase 1 完成後停止，經使用者確認才開始 Phase 2。
使用 feature branch；不自行 commit、push、merge 或變更 Git 身分。
依使用者授權才建立各階段 commit。

## API 使用參考

設定以官方文件為依據：[FastAPI 測試](https://fastapi.tiangolo.com/tutorial/testing/)、
[Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)、
[Vite](https://vite.dev/guide/)、[Tailwind Vite plugin](https://tailwindcss.com/docs/installation/using-vite)。
