# 資料庫設計

PostgreSQL 為正式目標，SQLAlchemy 2 同步 Session；每個請求獨立 Session。
UUID 主鍵，時間欄位 PostgreSQL TIMESTAMPTZ，連線 session timezone UTC。
migration 唯一真實來源；應用程式不呼叫 create_all。

## Phase 1 已建立

`0001_game_types` 建立 game_types：id UUID PK、code UNIQUE、name、min_players、
max_players、enabled、created_at；人數範圍 CHECK。唯一 code 自帶索引。
種入四種遊戲目錄（規格資料，非玩家／牌局假資料），全部停用。
十三支／五張抽牌人數暫為規格草案，開放前再確認。
Alembic 維護 alembic_version。Phase 1 沒有下注或結算資料與操作。

## 後續資料表（尚未 migration）

| 表 | 主要欄位／約束／索引 |
| --- | --- |
| users | id、登入識別 UNIQUE、password_hash、display_name、created_at |
| rooms | id、owner_id FK users、game_type_id FK、invite_code_hash UNIQUE、status、version、created_at；owner/status 索引 |
| room_members | id、room_id FK、user_id FK、seat、ready、joined_at；UNIQUE(room,user)、UNIQUE(room,seat) |
| game_sessions | id、room_id FK、game_type_id FK、rules_version、state_version、status、protected_snapshot、created_at；room/status 索引 |
| game_players | id、session_id FK、user_id FK、seat、initial_points、final_points；UNIQUE(session,user)、UNIQUE(session,seat) |
| game_events | id、session_id FK、actor_id FK users、seq、request_id、action_hash、protected_payload、created_at；UNIQUE(session,seq)、UNIQUE(session,actor,request_id) |
| game_results | id、session_id FK、player_id FK game_players、points_delta、rank、created_at；UNIQUE(session,player) |
| player_stats | id、user_id FK、game_type_id FK、games_played、wins、points；UNIQUE(user,game_type) |

session／user FK 均建索引。禁止連鎖刪除不可變事件與結算紀錄；會員退出不刪歷史。
邀請碼不可當成登入 token。保留政策、個資清除與封存需在公開部署前定案。

## 原子性、事件及恢復設計

以 session 行鎖序列化動作，檢查成員、輪次、request_id 及 state_version 後，
在單一 transaction 更新版本／快照、序號唯一的事件及（如結束）結果／統計。
更新使用預期版本條件；衝突 rollback，不以最後寫入覆蓋。
積分採整數，不採浮點；以積分守恆與負數限制測試結算。
重播需要固定規則版本、受保護初始牌序、確定性動作事件、快照版本及狀態校驗。
含手牌的 payload／snapshot 僅限後端與受控資料庫權限讀取。
Redis 將用於多實例廣播與連線狀態，不能取代 PostgreSQL 結算真實來源。

## Migration 與備份

`alembic upgrade head`；開發拋棄式資料庫以 `downgrade base` → `upgrade head` 測試。
正式 rollback 需事前備份與變更影響評估，不能直接沿用測試資料庫流程。
Phase 7 才驗證 pg_dump／pg_restore、事件重播恢復與 RPO/RTO。
目前已通過原生 PostgreSQL 17.12 的 migration 往返、UUID／UTC、唯一性／CHECK、
交易回滾與資料庫重啟資料保留／API 重連測試。測試使用獨立 schema 並在結束後清理，
可重跑。尚未做 Docker PostgreSQL、named volume、備份或恢復驗收。
