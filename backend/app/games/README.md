# 遊戲引擎邊界

目前實作 Phase 2 的 P2-A 牌組核心與 P2-B 純資料型別（`core/models.py`）；尚未提供可執行遊戲。
規則引擎不可匯入 FastAPI、SQLAlchemy、React 或瀏覽器 API。
預計分為 core、registry、texas_holdem、big_two、chinese_poker（僅介面）。

## P2-A 契約

- `Card(rank: Rank, suit: Suit)` 是不可變、可雜湊的值物件；不接受原始字串／數字自動轉型。
- `Card.from_code("AS")`／`card.code` 提供固定牌面碼往返，10 採 `10H`，只接受大寫、無空白。
- Suit 為 C／D／H／S，Rank 為 2～10／J／Q／K／A；沒有鬼牌。
  Enum 順序與數值不代表牌型強度或大老二花色順序；Card 沒有大小比較運算。
- `Deck()` 建立標準 52 張牌並立即以 `secrets.SystemRandom` 洗牌。
- `deal(count=1)` 回傳不可變 tuple，從牌序前端發出；`remaining_count` 是剩餘牌數。
  count=0 合法；負數、bool、非整數、超額發牌拒絕且不更改牌組。
- `shuffle()` 只洗剩餘牌，不放回已發牌；`reset()` 恢復完整牌組並重新安全洗牌。
- `Deck.for_testing(cards)` 明確注入固定首張至末張牌序，可為部分牌組或空牌組。
  複製輸入、拒絕非法元素／重複牌，重置後復原固定牌序。
  `is_test_only=True` 標記會保留，不能經公開屬性修改；沒有 seed／rng／關閉洗牌參數。
- 固定牌序工廠只供受信任測試程式使用；未來正式引擎接入時必須拒絕 test-only 牌組。
  此 Python API 標記用於避免誤用，不是抵禦任意 Python 程式竄改的安全隔離。
- Deck 每場獨立持有；不保證跨執行緒共用安全，牌序不記錄於 repr 或日誌。

## P2-B 內部資料契約

- 沿用 frozen dataclass 與 Enum，不依賴 Pydantic／資料庫／網頁，也不建立牌組或產生 UUID。
- `PlayerId` 是 UUID 的 Python 3.12 型別別名；以 `UUID(...)` 建立實際值。
- Player：id（使用者 UUID）、display_name、seat（0 起）、points（無現金價值的非負整數，預設 0）。
- GameStatus：waiting／in_progress／finished。只表示最小生命週期，不表示合法轉移或德州街道。
- Turn：player_id。沒有選擇下一位玩家、計時或操作狀態機。
- GameAction：player_id、request_id、state_version、type。只描述服務端動作中繼資料，
  未包含各遊戲的下注／出牌 payload，也不判斷動作是否合法。player_id 必須由後端認證綁定。
- GameError：code、message、可選 request_id。這是純資料，不是 Exception 或 HTTP 回應；
  code 的完整清單及安全訊息內容須由後續流程決定，不會自動遮蔽任意傳入字串。
- PublicGameData：status、state_version、players、turn；公開玩家只接受 `type(player) is Player`，
  不保留或自動轉換 Player 子類別；違反時拋出不含私有欄位內容的 TypeError。
  Turn 與 public 容器也在同一資料保留鏈使用精確型別檢查，防止額外欄位進入 asdict／repr。
  一般 Player、tuple、Turn 的物件參照與既有欄位保持不變；子類別不是受支援的公開 DTO。
- PrivatePlayerData：player_id、hand；PrivateGameData：私有玩家資料及 remaining_cards tuple。
  兩者均不提供發牌、洗牌、重播或持久化功能，私有牌面不顯示於 repr。
- GameState：session_id、game_type、rules_version、public、private，只能作服務端內部資料。
- PlayerView：viewer_id、public、單一 PrivatePlayerData；檢查私有資料的 owner 與 viewer 一致，
  但不做認證／授權或 get_player_view 投影。GameState／PlayerView 的 public 欄位拒絕
  PublicGameData 子類別，即使該子類別略過父類別驗證；沒有新增通用序列化或轉換流程。
- tuple 集合拒絕可變 list／dict；檢查必要欄位、UUID、非負整數、重複玩家／座位、
  單一牌集合重複與 owner／turn 成員關係。不驗證跨牌集合守恆、遊戲人數或牌局規則。
- 原始文件未定義逐欄 schema；以上為本輪採用的最小內部契約，不新增或改寫 REST／WS 格式。
  本輪沒有 dataclass JSON codec；API_SPEC 的巢狀 action envelope 仍待傳輸層與引擎契約階段實作。
  不得把 `asdict(GameState)` 當成公開輸出；repr=False 不代表一般序列化會移除私有欄位。

P2-A 的亂數失敗後 reset 風險、test-only 正式隔離、Python frozen 信任限制及完整回歸
版本追溯缺口仍保持開放。P2-B 沒有修正或取代這些防護。
Room／GameSession／GameEvent／GameResult 的獨立型別、六方法 Protocol、Registry、
牌型判斷或任何遊戲仍未實作；後續順序見 TASKS 與 Phase 2 進度報告。
