# 可玩原型（路徑 B）

單一程序、記憶體保存牌局的德州撲克原型，用來和朋友試玩引擎。**不是正式架構**：沒有真實認證、資料庫、
冪等、重連重播與逾時；牌局只存在後端記憶體，重啟即消失。不得對公網開放。

## 規則值（原型值，非核准政策）

小盲 5／大盲 10、每人 1000 積分、不燒牌；可用環境變數覆寫：
`PROTOTYPE_SMALL_BLIND`、`PROTOTYPE_BIG_BLIND`、`PROTOTYPE_STARTING_POINTS`、`PROTOTYPE_BURN_CARDS`。
正式值（契約政策 1、2、3）仍待確認。

## 執行

後端（預設關閉，須明確啟用）：

```bash
cd backend
PROTOTYPE_ENABLED=true ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：`cd frontend && npm run dev`，開啟 <http://127.0.0.1:5173>，按「瀏覽遊戲」，在德州撲克卡片按「建立或加入房間」。
一人建立房間並把五碼房間代碼給朋友；房主按「開始牌局」，每手結束後按「下一手」。

## 結構

- `backend/app/prototype/assembly.py`：啟動組裝，經 Registry 登記並取得引擎（不直接建構）。
- `backend/app/prototype/table.py`：成員、莊家輪替、牌局生命週期（結算只套用一次）、逐人視圖。
- `backend/app/prototype/routes.py`：`POST /api/proto/rooms`、`POST /api/proto/rooms/{code}/join`、
  `WS /api/proto/rooms/{code}/ws`（首則訊息 `{"token": ...}`；之後 `start`、`action`）。
- `frontend/src/Game.tsx`：大廳與牌桌。

## 視圖與資訊隔離

視圖只含公共牌、各座位公開資料、**本人**底牌，以及攤牌時亮出的牌；不含其他人的底牌或剩餘牌堆。
結算只顯示每座位的 `payout` 與最終籌碼（契約選項 A）；各池明細仍是未決政策 5。

## 已知限制

- token 是隨機不記名憑證，沒有帳號、限流或 Origin 檢查。
- 不處理逾時：有人離開，牌局會停在他的回合。
- 玩家只有在兩手之間才能加入；籌碼為 0 的玩家留在名單但不再入局。
- 一人籌碼耗盡後只剩一人時遊戲結束，沒有重新開始或補籌碼。

## 大老二私人試玩

於後端設定 `BIG_TWO_PROTOTYPE_ENABLED=true`，再依上方方式啟動服務。大廳的大老二卡片會顯示私人試玩入口。每桌需四位玩家都在線，再由房主開局。房間內的有號積分從零起算，可跨局累計。關閉或回收房間會清除該帳本。

大老二使用 `/api/proto/big-two` 下的狀態、建立、加入與 WebSocket 路徑。斷線保留原席位；離開後，從同一瀏覽器分頁再次進入大老二可嘗試恢復。全員連續離線滿 30 分鐘回收房間。每位成員、每局的最近 256 份動作回執只在房間及程序存活時保留。私人原型限受信任玩家使用。

完整前端回歸可從 `frontend/` 執行 `PROTOTYPE_ENABLED=true BIG_TWO_PROTOTYPE_ENABLED=true npm run test:e2e`。兩個設定均關閉時，可驗證大廳的停用狀態。
