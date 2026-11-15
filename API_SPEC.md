# API 規格

## Phase 1 已實作

- `GET /api/health/live` → 200 `{"status":"ok","phase":"1"}`，不依賴資料庫。
- `GET /api/health/ready` → 200 `{"status":"ready"}`；資料庫不可達、migration 版本
  或遊戲目錄筆數不符 → 503，僅回傳一般錯誤，不包含 SQL／憑證。
- `GET /docs`、`GET /openapi.json`：開發用 FastAPI 文件。
- 目前沒有認證、房間、遊戲、WebSocket 端點。

## 後續規劃（未實作）

REST `/api/v1`：登入／登出／me、建立與加入房間、座位、準備／開始、歷史、個人統計。
建立與加入需要身分驗證，邀請碼須有限速與不可列舉設計。
預計錯誤含 code、message、request_id；HTTP 401／403／404／409／422／429 語意分明。

WS `/api/v1/rooms/{room_id}/ws`：僅在驗證身分與房間成員後接受。
預計使用同站 HttpOnly Secure session cookie、Origin allowlist；不以 URL token 傳長期憑證。

客戶端動作格式：

```json
{"type":"action","request_id":"UUID","state_version":12,"action":{"type":"call"}}
```

伺服器回應格式（規劃）：

```json
{"type":"player_view","request_id":"UUID","state_version":13,"event_seq":26,"view":{}}
```

view 必須經引擎 get_player_view 逐人投影；不可廣播內部 state。
同一成員與 session 下 request_id 唯一；重送回傳原授權結果，不重複處理。
不同 payload 重用同一 id 拒絕；過期版本返回 stale_state 與新的授權視圖。
服務端以交易、行鎖與版本條件更新，同一交易寫事件、結果及統計。
重連先重新檢查身分與會員權限，再回最新投影和缺失的公開／本人事件。
限流、payload 大小、心跳、閒置／斷線輪次逾時策略於 Phase 5 實作與測試。
