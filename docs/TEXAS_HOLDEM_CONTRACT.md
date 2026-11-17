# 德州撲克規則契約（P3-05）

本文件把德州撲克規則整理成**可測試的條款**。每個條款有編號、來源、狀態，以及對應的測試；
`backend/tests/games/test_texas_contract_traceability.py` 會解析下方的條款表，檢查編號唯一、狀態合法、
每個非 OPEN 條款至少有一個**真實存在**的測試，且 OPEN 條款不得宣稱已有測試。

## 一、狀態定義（不得混用）

| 狀態 | 意義 |
| --- | --- |
| SPEC | 原始規格（`GAME_RULES.md`、`API_SPEC.md`、`SECURITY.md`、`DATABASE.md`）明確寫出 |
| APPROVED | 專案紀錄中已由使用者明確批准（`PHASE_2.md` 各階段決策，含「照建議」），且不屬於下方列出的待確認政策 |
| CHOSEN | 規格未定義，由實作採用的選擇；**已實作並有測試，但仍待人工確認，不得當成既定規則** |
| OPEN | 沒有核准的政策；**不得由程式碼反向定義**，目前沒有（或不應有）對應行為 |

來源欄中的 `GAME_RULES l.N` 指 `GAME_RULES.md` 的行號（P3-05 複驗後已逐行對照更正）；`P3-0N 決策 k` 指 `docs/reports/PHASE_2.md` 該階段章節的決策項。

## 二、條款表

| ID | 條款 | 來源 | 狀態 | 測試 |
| --- | --- | --- | --- | --- |
| R1.1 | 牌組為標準 52 張、無鬼牌、牌彼此相異 | GAME_RULES l.5 | SPEC | test_deck.py::test_standard_deck_has_exactly_52_distinct_cards; test_card.py::test_standard_faces_are_exactly_the_required_sets |
| R1.2 | 洗牌使用作業系統安全亂數；亂數失敗時牌組不可再發牌，直到重置或洗牌成功 | GAME_RULES l.5；P3-00 | SPEC | test_deck.py::test_production_create_reset_and_shuffle_always_use_system_random; test_deck_failure_and_isolation.py::test_failed_reset_leaves_the_deck_unable_to_deal_until_recovery |
| R1.3 | 引擎只接受精確、完整、可用、非測試用的牌組；不接受客戶端提供的牌序 | SECURITY l.17；P2-C | SPEC | test_engine_contract.py::test_production_deck_is_accepted_and_others_rejected; test_texas_setup.py::test_start_hand_requires_a_production_deck_but_the_testing_path_does_not |
| R1.4 | 底牌從小盲起順時針每人一張、共兩輪發出 | 規格未定義；P3-01 決策 5 | CHOSEN | test_texas_setup.py::test_deal_order_and_rotation_with_a_known_deck; test_texas_setup.py::test_heads_up_deals_from_the_button_who_is_also_the_small_blind |
| R1.5 | 手牌、未發牌堆與公共牌中沒有任何一張牌出現兩次 | P2-F 契約套件 | APPROVED | test_texas_engine.py::test_random_playouts_always_finish_with_valid_states |
| R2.1 | 一手牌 2 到 9 人 | GAME_RULES l.13 | SPEC | test_texas_setup.py::test_start_hand_for_every_table_size; test_texas_setup.py::test_expected_rejections_are_data |
| R2.2 | 座位為互異的非負整數，可有空號，編號遞增為順時針 | P3-01 決策 4 | CHOSEN | test_texas_setup.py::test_invalid_seat_sets_are_rejected; test_texas_setup.py::test_repeated_seats_are_rejected_even_when_the_button_is_valid |
| R2.3 | `Player.points` 為本手開始時的桌上籌碼；少於 1 的玩家不能入局 | P3-01 決策 6 | CHOSEN | test_texas_setup.py::test_expected_rejections_are_data; test_texas_setup.py::test_start_hand_leaves_players_untouched_and_orders_seats |
| R2.4 | 籌碼為非負整數積分 | GAME_RULES l.13（整數積分；PRD l.6 只說積分無現金價值，不是整數的依據） | SPEC | test_texas_raising.py::test_every_invalid_amount_or_payload_is_rejected_without_changing_the_state |
| R2.5 | 籌碼最小單位，以及整數以外的合法金額（例如是否須為盲注的倍數） | 無依據 | OPEN | none |
| R3.1 | 單挑：按鈕即小盲，翻牌前先行；翻牌後大盲先行 | GAME_RULES l.14 | SPEC | test_texas_setup.py::test_positions_match_the_hand_written_table; test_texas_engine.py::test_heads_up_check_down_with_known_board_and_events |
| R3.2 | 三人以上：小盲在按鈕左側，大盲在小盲左側，翻牌前第一位行動者在大盲左側 | 規格只說盲注與按鈕輪替；P3-01 | CHOSEN | test_texas_setup.py::test_position_invariants_for_every_size_and_button |
| R3.3 | 第一手的按鈕是最小座位號，之後依座位順時針輪替 | 規格未定義；P3-01 決策 3 | CHOSEN | test_texas_setup.py::test_rotation_visits_every_seat_in_a_cycle_for_every_table_size; test_texas_engine.py::test_rotating_the_button_changes_the_first_actor |
| R3.4 | 小盲與大盲的金額，以及設定的存放方式 | GAME_RULES l.22 只要求版本化設定，無數值 | OPEN | none |
| R3.5 | 籌碼不足盲注時，投入全部籌碼並視為 all-in | 規格未定義；P3-01 決策 7 | CHOSEN | test_texas_setup.py::test_short_stacks_post_what_they_have_and_are_all_in |
| R3.6 | 產品程式不含預設盲注、籌碼或燒牌值，由呼叫端以規則物件提供 | P3-01 決策 1 | APPROVED | test_texas_setup.py::test_product_modules_do_not_define_rule_values; test_texas_registry.py::test_registration_helpers_have_exactly_the_documented_signatures |
| R4.1 | 是否燒牌的政策值 | GAME_RULES l.22 只要求版本化設定，無數值 | OPEN | none |
| R4.2 | 規則物件的 `burn_cards` 為真時，翻牌、轉牌、河牌前各燒一張；為假時不燒 | 旗標語意；P3-02 決策 3 | CHOSEN | test_texas_engine.py::test_burn_cards_are_skipped_before_each_street |
| R5.1 | 街順序為翻牌前、翻牌（3 張）、轉牌（1 張）、河牌（1 張）、攤牌 | GAME_RULES l.15 | SPEC | test_texas_engine.py::test_heads_up_check_down_with_known_board_and_events |
| R5.2 | 可行動座位少於兩個時不再下注，剩餘各街直接發完（含建局時） | 規格未定義；P3-02／P3-03 | CHOSEN | test_texas_engine.py::test_everyone_all_in_runs_the_board_out_without_betting; test_texas_engine.py::test_a_hand_where_nobody_can_act_from_the_start_is_dealt_out_at_creation; test_texas_raising.py::test_a_lone_active_seat_with_nothing_to_answer_is_dealt_out_at_creation |
| R5.3 | 只剩一個未棄牌座位時牌局立即結束，不需攤牌 | TASKS P3-02（全棄牌） | APPROVED | test_texas_engine.py::test_everyone_folds_to_the_big_blind; test_texas_engine.py::test_fold_on_the_flop_ends_the_hand_without_a_showdown |
| R6.1 | 動作為棄牌、過牌、跟注、下注、加注、全下 | GAME_RULES l.16 | SPEC | test_texas_engine.py::test_legal_actions_in_representative_spots |
| R6.2 | 不足跟注額時可全下，視為跟注 | GAME_RULES l.16 | SPEC | test_texas_engine.py::test_short_all_in_call_keeps_the_hand_going_for_the_others |
| R6.3 | 下注與加注的金額為「加到」：該座位本街投入的總額 | P3-03 決策 1 | APPROVED | test_texas_raising.py::test_heads_up_bet_raise_and_short_all_in_chain; test_texas_raising.py::test_a_raise_to_the_full_stack_is_flagged_all_in |
| R6.4 | 最低下注為大盲；最低加注增量為上一次完整加注的大小（至少大盲），每街重置 | P3-03 決策 2 | APPROVED | test_texas_raising.py::test_preflop_raise_chain_updates_the_minimum_each_time; test_texas_blinds.py::test_every_street_resets_the_minimum_to_the_big_blind |
| R6.5 | 重新開放：座位只有在下注自它上次行動起增加至少一個最低增量時才能再加注；單一短額 all-in 不重新開放，多個累計達完整加注則重新開放 | P3-03 決策 3；GAME_RULES l.17 要求明確處理 | APPROVED | test_texas_raising.py::test_a_short_all_in_does_not_reopen_the_action_for_the_raiser; test_texas_raising.py::test_several_short_all_ins_that_add_up_to_a_full_raise_reopen_the_action |
| R6.6 | 大盲不足額時，翻牌前最低加注到 max(目前下注, 大盲) 加最低增量 | P3-03 決策 4 | APPROVED | test_texas_raising.py::test_a_short_big_blind_still_means_a_minimum_raise_to_twice_the_blind; test_texas_blinds.py::test_a_short_big_blind_still_means_a_raise_to_twice_the_big_blind |
| R6.7 | 對手全部 all-in 或棄牌的座位不能下注或加注，只能跟注或棄牌 | P3-03 實作選擇 | CHOSEN | test_texas_raising.py::test_nobody_can_bet_or_raise_against_opponents_who_are_all_all_in; test_texas_blinds.py::test_a_seat_cannot_raise_when_the_opponents_left_are_folded_or_all_in |
| R6.8 | 能過牌時仍可棄牌；翻牌前大盲保有選擇權 | P3-02 決策 4、8 | CHOSEN | test_texas_engine.py::test_big_blind_keeps_its_option_and_postflop_spots_allow_check_or_fold |
| R6.9 | 非法動作以資料回傳，絕不改變狀態，錯誤訊息不含牌面 | P2-C（`GameError` 的訊息必須可公開；SECURITY l.19 只規範日誌，不涵蓋錯誤訊息） | APPROVED | test_texas_engine.py::test_rejections_use_stable_codes_and_never_change_the_state; test_texas_engine.py::test_error_messages_never_name_cards |
| R6.10 | 下注與加注金額含上下限；超出範圍回傳 `bad_amount` | P3-03 | APPROVED | test_texas_raising.py::test_amount_boundaries_are_inclusive; test_texas_raising.py::test_every_invalid_amount_or_payload_is_rejected_without_changing_the_state |
| R7.1 | 按貢獻分層建主池與邊池；棄牌的貢獻保留但不得獲池；退回未被跟注的部分 | GAME_RULES l.20 | SPEC | test_texas_settlement.py::test_example_1_one_short_all_in_makes_a_main_pot_and_a_side_pot; test_texas_settlement.py::test_example_2_an_uncalled_bet_is_returned_before_the_pot_is_built; test_texas_settlement.py::test_example_3_folded_chips_count_but_never_win_and_equal_layers_merge |
| R7.2 | 相鄰且有資格座位完全相同的層，先合併再分配 | 規格未定義；P3-04 契約（政策 4，待人工再確認） | CHOSEN | test_texas_settlement.py::test_example_5_two_layers_with_the_same_eligible_seats_are_one_pot |
| R7.3 | 平手均分，餘數依按鈕左側順時針順序分配 | GAME_RULES l.21 | SPEC | test_texas_settlement.py::test_example_4_the_odd_chip_goes_clockwise_after_the_button |
| R7.4 | 按鈕座位若為贏家，最後取得奇數籌碼；每個池各自計算餘數 | GAME_RULES l.21 的細節補充（政策 4） | CHOSEN | test_texas_settlement.py::test_the_button_seat_gets_an_odd_chip_last |
| R7.5 | 只有一個有資格座位的池直接歸它，不比牌 | P3-04 | APPROVED | test_texas_settlement.py::test_a_lone_live_seat_wins_everything_without_any_strength |
| R7.6 | 最佳五張自七張組成 | GAME_RULES l.18 | SPEC | test_texas_seven.py::test_hand_worked_cases; test_texas_seven.py::test_random_hands_agree_with_the_independent_evaluator |
| R7.7 | A 可作 A2345 的低牌（不環繞）；花色不作同牌型勝負依據 | GAME_RULES l.19 | SPEC | test_texas_hands.py::test_no_wraparound_straights_are_not_straights; test_texas_hands.py::test_ties_ignore_suits_for_every_category |
| R7.8 | 所有結算保持積分守恆 | GAME_RULES l.21 | SPEC | test_texas_settlement.py::test_pots_are_conserved_never_won_by_folded_seats_and_awarded_in_full |
| R8.1 | 攤牌時所有未棄牌座位公開底牌；只剩一個座位時不公開 | 規格未定義；P3-04 決策 2（待人工再確認） | CHOSEN | test_texas_settlement.py::test_shown_hands_are_the_real_hole_cards_of_the_seats_still_in; test_texas_settlement.py::test_a_folded_hand_is_never_shown_and_the_survivor_takes_the_pot |
| R8.2 | 結果的 `points_delta` 為淨籌碼變動；名次為競賽排名（依變動由高到低，並列同名次） | DATABASE 有 rank 欄位但未定義；P3-04 決策 3（待人工再確認） | CHOSEN | test_texas_settlement.py::test_ranks_share_a_place_for_equal_results; test_texas_engine.py::test_result_is_unavailable_until_the_hand_is_over_and_then_settles |
| R9.1 | `settle_state` 只計算，不改變狀態；同一狀態重複計算結果相同 | P3-04 決策 4 | APPROVED | test_texas_settlement.py::test_settlement_does_not_change_the_state_and_is_repeatable; test_texas_settlement_apply.py::test_computing_and_applying_are_separate_responsibilities |
| R9.2 | `apply_settlement`／`settle_hand` 只套用一次，第二次套用被拒絕；金額一律由狀態重新計算（「不接受外部結算」本身見 R9.8） | P3-05 設計 | CHOSEN | test_texas_settlement_apply.py::test_a_second_application_is_refused_and_changes_nothing; test_texas_settlement_apply.py::test_nothing_in_the_interface_accepts_a_settlement_from_outside |
| R9.3 | 套用後：每座位的 `payout` 與 `stack` 更新、`TexasPublic.settled` 為真、狀態版本加一、發出一個 `HandSettled` 事件 | P3-05 設計 | CHOSEN | test_texas_settlement_apply.py::test_settlement_moves_the_chips_marks_the_hand_and_emits_one_event |
| R9.4 | 套用後籌碼守恆：各座位 `payout` 之和等於底池，`stack` 等於起始積分減投入加 `payout`；不一致的狀態無法建構 | P3-05 設計；GAME_RULES l.21 | CHOSEN | test_texas_settlement_apply.py::test_random_hands_conserve_chips_and_match_the_independent_settlement; test_texas_settlement_apply.py::test_inconsistent_settlements_cannot_be_constructed |
| R9.5 | 結算後不能再有任何動作 | P3-05 設計 | CHOSEN | test_texas_settlement_apply.py::test_no_action_is_possible_after_the_settlement |
| R9.6 | 整手牌的事件序號無缺口、不重複；`HandEnded` 之後才是 `HandSettled`，後者為最後一個事件 | P3-05 設計 | CHOSEN | test_texas_settlement_apply.py::test_a_whole_hand_has_one_gapless_event_sequence_ending_with_the_settlement |
| R9.7 | 結算明細（各池金額、資格、得主、牌型名稱）哪些要公開、何時公開 | 無依據（政策 5） | OPEN | none |
| R9.8 | 不接受客戶端或外部提供的結算結果；結算介面只接收狀態 | SECURITY l.17（拒絕客戶端…結算結果） | SPEC | test_texas_settlement_apply.py::test_nothing_in_the_interface_accepts_a_settlement_from_outside |
| R10.1 | 底牌與未發牌堆為私有，只在符合攤牌條件時公開；結算後亦然 | GAME_RULES l.9；SECURITY l.20 | SPEC | test_texas_engine.py::test_views_show_the_board_but_never_hole_cards_or_the_deck; test_texas_settlement_apply.py::test_views_of_a_settled_hand_show_only_what_may_be_public |
| R10.2 | 視圖由伺服器依狀態逐人投影；客戶端不決定結算結果 | API_SPEC l.32 | SPEC | test_texas_engine.py::test_projection_of_every_state_in_a_hand_is_valid_for_every_player; test_texas_settlement_apply.py::test_nothing_in_the_interface_accepts_a_settlement_from_outside |
| R11.1 | 引擎以代碼 `texas_holdem` 登記，玩家人數範圍與 `game_types` 目錄一致（2 到 9） | P2-D；DATABASE l.9–10（人數範圍欄位；數值見 migration `0001_game_types`） | APPROVED | test_texas_registry.py::test_the_registration_record_matches_the_game_catalog |
| R11.2 | 重複登記與未知代碼以 `GameError` 回傳，且不覆蓋、不回顯輸入 | P2-D | APPROVED | test_texas_registry.py::test_a_duplicate_registration_is_an_error_and_keeps_the_first; test_texas_registry.py::test_unknown_and_unimplemented_games_stay_unknown |
| R11.3 | 應用程式碼只能經登記輔助函式建立引擎，不得直接建構而繞過 Registry | P3-05 | APPROVED | test_texas_registry.py::test_the_engine_is_only_built_by_the_registration_helper |
| R11.4 | 沒有全域預設 Registry，也沒有預設登記或預設規則 | P2-D；P3-01 決策 1 | APPROVED | test_texas_registry.py::test_registries_are_independent_and_nothing_is_registered_by_default |

## 三、尚未確認的政策：依據、缺口、候選與程式影響

以下五項**不是既定規則**。每項先列既有依據與缺口，再列候選與實際的程式影響。標示「阻擋」的部分已停止實作，等待使用者確認。

### 政策 1：燒牌

- **既有依據**：`GAME_RULES.md` l.22 要求「燒牌…需以版本化設定記錄」；`TexasRules.burn_cards` 為必填布林；P3-02 決策 3 把它暫定為 False 並標為待確認。
- **缺口**：沒有任何核准的值。
- **候選**：(a) 翻牌、轉牌、河牌前各燒一張；(b) 不燒牌。
- **程式影響**：只改規則物件的一個欄位，公共牌的取牌位置不同；固定牌序測試的期望值要跟著規則版本記錄；牌組中被燒的牌目前不保留在狀態中（重播依賴受保護的初始牌序）。
- **是否阻擋**：不阻擋實作。登記輔助函式接受呼叫端提供的規則，產品程式不含預設值；但**正式組裝（啟動時建立 Registry）需要核准值**，這部分待你確認。

### 政策 2：盲注數值與設定方式

- **既有依據**：同上，`GAME_RULES.md` l.22 只要求版本化設定；`DATABASE.md` 的 `game_sessions.rules_version` 記錄規則版本；`game_types` 資料表沒有盲注欄位。
- **缺口**：數值，以及設定存放位置。
- **候選**：(a) 每個規則版本在程式中固定一組數值；(b) 每個房間可設定，存在牌局設定中（需要資料庫結構，屬 Phase 5）。
- **程式影響**：`TexasRules("版本", 小盲, 大盲, 燒牌)` 的建立位置；`register_texas_holdem` 的呼叫端；測試目前使用標為 fixture 的 5/10。
- **是否阻擋**：不阻擋機制，**阻擋正式組裝**。

### 政策 3：籌碼最小單位與合法值

- **既有依據**：「整數積分」（`GAME_RULES.md` l.13；`PRD.md` 只說積分無現金價值）；實作目前以 1 為最小單位，任何大於等於最低值的整數都合法。
- **缺口**：最小單位是否大於 1；下注與加注是否須為某單位（例如小盲）的倍數；平分時單位是否影響餘數。
- **候選**：(a) 單位 1（現況）；(b) 單位等於小盲，所有金額須為其倍數。
- **程式影響**：`bad_amount` 的檢查、最低加注計算、結算平分的餘數（奇數籌碼）；若改為 (b)，既有的金額測試與結算範例都要重新審視。
- **是否阻擋**：不阻擋；維持現況不是決定，**條款 R2.5 保持 OPEN**。

### 政策 4：邊池合併與奇數籌碼

- **既有依據**：奇數籌碼的「按鈕左側順時針」在 `GAME_RULES.md` l.21 明確；「合併相鄰同資格層」與「按鈕座位最後」**不在規格中**，來自 P3-04 設計審查（使用者以「照建議」批准），P3-04 結案時又標為須人工再確認。
- **缺口**：規格沒有說明資格相同的相鄰層是否合併。
- **候選**：(a) 合併後再分配（現況）；(b) 每層各自分配。兩者在 2.60% 的有多池桌子（隨機樣本）會讓某位玩家多或少一枚籌碼；例如兩位棄牌者各投入 3、三位有效玩家各投入 10 且兩位平手，(a) 為 18/18，(b) 為 19/17。
- **程式影響**：`settlement.build_pots` 的合併步驟與三份獨立參考；改為 (b) 時要同步改測試範例 5。
- **是否阻擋**：不阻擋；**維持現況並標為 CHOSEN**，不得視為已確認的規則。

### 政策 5：結算明細的公開範圍與時機

- **既有依據**：`API_SPEC.md` l.32（視圖須逐人投影）、`GAME_RULES.md` l.9（不得暴露他人底牌或剩餘牌堆）、`SECURITY.md`（公開歷史不含仍應保密的手牌）。
- **缺口**：結算後哪些資訊對所有玩家公開：各池金額與資格、得主、牌型名稱、退回金額；以及何時公開（牌局結束的同一步，或另一步）。
- **候選**：(A) 最小：只有最終籌碼、各座位 `payout` 與 `settled` 標記（現況；這些都可由公開狀態推導，不新增任何揭露）；(B) 加上各池的金額、資格與得主；(C) 再加上亮牌者的牌型名稱。
- **程式影響**：`HandSettled` 事件的內容、`TexasPublic` 是否增加池明細欄位、視圖投影與洩漏測試（亮牌豁免）。
- **是否阻擋**：**阻擋 (B)、(C) 的事件內容與池明細公開**，這部分已停止實作。現況只實作 (A) 的機制：`HandSettled` 事件**不帶任何明細**（只是標記），明細公開為 OPEN（條款 R9.7）。

## 四、結算的套用與公開流程（已實作的部分）

1. 牌局結束（`GameStatus.FINISHED`，`TexasPublic.ended` 為 `LAST_STANDING` 或 `SHOWDOWN`）：由 `apply_action` 完成，狀態中的 `stack` 仍是「起始積分減投入」，`pot` 為全部投入，`payout` 全為 0，`settled` 為假。此時 `calculate_result` 與 `settle_state` 可純計算結果。
2. 驅動牌局的伺服器端呼叫 `TexasEngine.settle_hand(state)`（內部使用 `apply_settlement`）：
   - 金額一律由狀態重新計算（`settle_state`），沒有接收外部結算的參數；
   - 每個座位 `stack` 加上 `payout`（退回加獲得），`all_in` 旗標改為「籌碼為 0」；
   - `settled` 設為真，狀態版本加一，事件序號加一，發出一個 `HandSettled` 事件；
   - 再次呼叫回傳 `already_settled`，狀態不變。
3. 結算後的不變式（由 `TexasPublic` 與其一致性檢查強制）：各座位 `payout` 之和等於 `pot`；每座位 `stack` 等於 `Player.points − committed + payout`；總籌碼等於起始總積分；棄牌座位的 `payout` 為 0；未結算時所有 `payout` 為 0。
4. 事件順序：…最後一個動作的事件、`StreetDealt`（若有）、`HandEnded`，然後（另一步）`HandSettled`。整手牌的事件序號無缺口。
5. 公開範圍（現況）：`SeatState.payout`、`stack`、`TexasPublic.settled`（皆可由公開狀態推導）；亮牌者的底牌（R8.1）；其餘結算明細不公開（政策 5，OPEN）。

## 五、需要使用者確認的具體事項

1. **政策 1、2（燒牌與盲注）**：核准的值與設定方式。這是**正式組裝（建立啟動用 Registry）的前置條件**；目前不存在也不應存在預設值。
2. **政策 5**：選擇 (A)（維持現況）、(B) 或 (C)，並決定明細公開的時機（與 `HandEnded` 同一步，或另一步）。
3. **政策 4**：確認維持「合併後再分配」，或改為各層各自分配。
4. **政策 3**：確認最小籌碼單位。
5. **條款 R9.2 到 R9.6** 是本階段新增的設計（套用一次、標記、事件）：請確認「牌局結束與套用結算分成兩步」是否符合預期，或希望在牌局結束的同一步自動套用（這會改變既有的最後事件順序與測試）。
