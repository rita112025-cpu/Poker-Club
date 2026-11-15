# 安全邊界

## Phase 1 現況

僅公開健康檢查與開發文件，沒有登入、房間或可用 WS。
設定由環境變數讀取；.env 忽略提交；.env.example 的密碼僅作佔位。
DB 故障回應不暴露底層錯誤；容器 API 停用 access log。
資料庫只綁 localhost，API 透過內網由 Nginx 存取；不公開 8000。
Nginx 有 nosniff、CSP、Referrer-Policy；目前僅 HTTP 開發部署，不代表完成安全驗收。

## Phase 5 必須實作

- 使用安全密碼雜湊及服務端 session，cookie 為 HttpOnly／Secure／SameSite。
- 每次 REST／WS 驗證身分、房間資格、座位、輪次、合法操作。
- WS Origin 驗證、CSRF 防護策略、登入／邀請碼／操作限流及訊息大小限制。
- request_id 冪等、state_version CAS、唯一序號、原子結算、交易失敗恢復。
- 後端安全亂數洗牌；拒絕客戶端牌序、手牌與結算結果。
- 視圖逐人產生，公開投影與私有事件分離；重連重新授權。
- 日誌不得包含牌序、底牌、完整狀態、cookie、token、密碼或資料庫 URL。
- 公開歷史不包含仍應保密的手牌，資料存取採最小權限。
- 多實例啟用前建置 Redis 同步及集中式限流；目前只允許單 API worker。

## Phase 7 部署檢查

TLS、信任的 proxy、正式 cookie、來源限制、秘密輪替、資料庫備份、依賴弱點、
越權／重播／競態／隱藏牌測試、壓力與斷線測試。
不記錄敏感狀態的同時，保留 request_id 與一般錯誤碼供稽核。
沒有執行過的檢查不得標記通過。
