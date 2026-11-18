import { useEffect, useRef, useState } from 'react'

// PROTOTYPE client: talks to /api/proto (in-memory table, bearer token, no accounts).

type Legal = { kinds: string[]; to_call: number; min_to: number | null; max_to: number | null }
type Seat = {
  player_id: string; nickname: string; seat: number; stack: number; committed: number
  street_committed: number; folded: boolean; all_in: boolean; payout: number
  button: boolean; small_blind: boolean; big_blind: boolean; cards: string[] | null
}
type GameView = {
  state_version: number; street: string; board: string[]; pot: number; current_bet: number
  over: boolean; settled: boolean; ended: string; turn: string | null; legal: Legal | null
  seats: Seat[]
}
type Member = { id: string; nickname: string; stack: number; connected: boolean; host: boolean }
type View = {
  type: 'view'; room: string; you: string; is_host: boolean; hand_no: number
  blinds: [number, number]; members: Member[]
  summary: { nickname: string; net: number; stack: number }[]; game: GameView | null
}
type ServerError = { type: 'error'; code: string; message: string }
type Session = { room: string; token: string }

const STORAGE_KEY = 'poker-proto-session'
const STREETS: Record<string, string> = {
  pre_flop: '翻牌前', flop: '翻牌', turn: '轉牌', river: '河牌', showdown: '攤牌',
}
const ACTION_LABEL: Record<string, string> = {
  fold: '棄牌', check: '過牌', call: '跟注', bet: '下注', raise: '加注', all_in: '全下',
}
const ERROR_TEXT: Record<string, string> = {
  not_host: '只有房主可以開始牌局', not_enough_players: '至少需要兩位有籌碼的玩家',
  hand_in_progress: '牌局進行中', not_your_turn: '還沒輪到你', stale_state: '畫面已過期，請重試',
  bad_amount: '金額超出允許範圍', illegal_action: '現在不能做這個動作', name_taken: '暱稱已被使用',
  bad_nickname: '暱稱需為 1 到 16 個字', table_full: '牌桌已滿',
}

function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw === null) return null
    const value: unknown = JSON.parse(raw)
    if (typeof value === 'object' && value !== null && 'room' in value && 'token' in value &&
      typeof value.room === 'string' && typeof value.token === 'string') {
      return { room: value.room, token: value.token }
    }
  } catch { /* storage unavailable or corrupt: start fresh */ }
  return null
}

function saveSession(session: Session | null) {
  try {
    if (session === null) sessionStorage.removeItem(STORAGE_KEY)
    else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch { /* ignore */ }
}

function errorMessage(code: string, fallback: string): string {
  return ERROR_TEXT[code] ?? fallback
}

function CardFace({ code }: { code: string | null }) {
  if (code === null) return <span className="card card-down" role="img" aria-label="暗牌" />
  const suit = code.slice(-1)
  const rank = code.slice(0, -1)
  const symbol: Record<string, string> = { S: '♠', H: '♥', D: '♦', C: '♣' }
  const red = suit === 'H' || suit === 'D'
  return (
    <span className={`card ${red ? 'card-red' : 'card-black'}`} role="img" aria-label={`${rank}${symbol[suit] ?? suit}`}>
      {rank}{symbol[suit] ?? suit}
    </span>
  )
}

function RoomEntry({ onJoined, onBack }: { onJoined: (session: Session) => void; onBack: () => void }) {
  const [nickname, setNickname] = useState('')
  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function enter(path: string) {
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch(path, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname }), signal: AbortSignal.timeout(8000),
      })
      const body: unknown = await response.json()
      if (!response.ok) {
        const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : null
        if (typeof detail === 'object' && detail !== null && 'code' in detail && 'message' in detail &&
          typeof detail.code === 'string' && typeof detail.message === 'string') {
          setMessage(errorMessage(detail.code, detail.message))
        } else {
          setMessage(response.status === 404 ? '找不到這個房間' : '無法加入，請稍後再試')
        }
        return
      }
      if (typeof body === 'object' && body !== null && 'room' in body && 'token' in body &&
        typeof body.room === 'string' && typeof body.token === 'string') {
        onJoined({ room: body.room, token: body.token })
      }
    } catch {
      setMessage('無法連線至伺服器（後端需設定 PROTOTYPE_ENABLED=true）')
    } finally {
      setBusy(false)
    }
  }

  const ready = nickname.trim().length > 0 && !busy
  return (
    <section className="mx-auto max-w-md space-y-5 rounded-xl border border-club-line bg-club-surface p-6">
      <button type="button" className="settings-trigger" disabled={busy} onClick={onBack}>返回遊戲大廳</button>
      <h2 className="text-xl font-medium text-club-accent">德州撲克（原型）</h2>
      <label className="block text-sm text-club-muted">暱稱
        <input className="mt-1 w-full rounded-md border border-club-line bg-transparent px-3 py-2"
          aria-label="暱稱" value={nickname} maxLength={16} onChange={(event) => { setNickname(event.target.value) }} />
      </label>
      <button className="w-full rounded-md border border-club-accent px-4 py-2 text-club-accent disabled:opacity-40"
        disabled={!ready} onClick={() => { void enter('/api/proto/rooms') }}>建立房間</button>
      <div className="flex gap-2">
        <input className="min-w-0 flex-1 rounded-md border border-club-line bg-transparent px-3 py-2 uppercase"
          placeholder="房間代碼" aria-label="房間代碼" value={code} maxLength={5}
          onChange={(event) => { setCode(event.target.value.toUpperCase()) }} />
        <button className="rounded-md border border-club-line px-4 py-2 disabled:opacity-40"
          disabled={!ready || code.length !== 5}
          onClick={() => { void enter(`/api/proto/rooms/${code}/join`) }}>加入</button>
      </div>
      <p role="status" className={`min-h-6 text-sm ${busy ? 'text-club-muted' : 'text-club-error'}`}>
        {busy ? '房間請求處理中，請稍候…' : message}
      </p>
      <p className="text-xs leading-6 text-club-muted">原型：盲注 5／10、每人 1000 積分，僅供好友試玩，積分無現金價值。牌局只存在伺服器記憶體中。</p>
    </section>
  )
}

function Controls({ game, send }: { game: GameView; send: (message: object) => void }) {
  const legal = game.legal
  const [amount, setAmount] = useState<number | null>(null)
  if (legal === null) return null
  const low = legal.min_to ?? 0
  const high = legal.max_to ?? 0
  const chosen = Math.min(Math.max(amount ?? low, low), high)
  const sizing = legal.kinds.includes('bet') ? 'bet' : legal.kinds.includes('raise') ? 'raise' : null
  function act(kind: string, value?: number) {
    send({ type: 'action', action: kind, amount: value ?? null, state_version: game.state_version })
  }
  return (
    <div className="space-y-3 rounded-lg border border-club-line p-4">
      <p className="text-sm text-club-accent">輪到你了{legal.to_call > 0 ? `・需跟注 ${legal.to_call}` : ''}</p>
      <div className="flex flex-wrap gap-2">
        {legal.kinds.filter((kind) => kind !== 'bet' && kind !== 'raise').map((kind) => (
          <button key={kind} className="rounded-md border border-club-line px-4 py-2 hover:bg-club-hover"
            onClick={() => { act(kind) }}>{ACTION_LABEL[kind] ?? kind}</button>
        ))}
      </div>
      {sizing !== null && (
        <div className="flex flex-wrap items-center gap-3">
          <input type="range" className="w-full max-w-40" min={low} max={high} value={chosen} aria-label="金額"
            onChange={(event) => { setAmount(Number(event.target.value)) }} />
          <input type="number" min={low} max={high} value={chosen} aria-label="金額數字"
            className="w-24 rounded-md border border-club-line bg-transparent px-2 py-1"
            onChange={(event) => { setAmount(Number(event.target.value)) }} />
          <button className="rounded-md border border-club-accent px-4 py-2 text-club-accent"
            onClick={() => { act(sizing, chosen) }}>{ACTION_LABEL[sizing]}到 {chosen}</button>
        </div>
      )}
    </div>
  )
}

function Table({ view, send }: { view: View; send: (message: object) => void }) {
  const game = view.game
  const active = view.members.filter((member) => member.stack > 0).length
  const canStart = view.is_host && (game === null || game.over) && active >= 2
  const names = new Map(view.members.map((member) => [member.id, member.nickname]))
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-club-muted">
        <span>房間代碼 <strong className="tracking-widest text-club-accent">{view.room}</strong>（分享給朋友）</span>
        <span>盲注 {view.blinds[0]}／{view.blinds[1]}・第 {view.hand_no} 手</span>
      </div>

      {game === null && (
        <ul className="space-y-1 text-club-muted">
          {view.members.map((member) => (
            <li key={member.id}>{member.nickname}{member.host ? '（房主）' : ''}・{member.stack} 積分
              {member.connected ? '' : '・離線'}</li>
          ))}
        </ul>
      )}

      {game !== null && (
        <div className="live-table space-y-5 rounded-2xl border p-3 sm:p-5">
          <p className="table-status text-center text-sm text-club-accent" aria-live="polite">
            <span className="preview-chip" aria-hidden="true" />
            {STREETS[game.street] ?? game.street}・底池 {game.pot}
            {game.over ? '・本手結束' : game.turn === view.you ? '・輪到你' : `・等待 ${names.get(game.turn ?? '') ?? ''}`}
          </p>
          <div className="community-cards flex min-h-16 justify-center gap-1 sm:gap-2" role="group" aria-label="公共牌">
            {game.board.map((code) => <CardFace key={code} code={code} />)}
          </div>
          <ul className="table-seats grid gap-3">
            {game.seats.map((seat) => {
              const mine = seat.player_id === view.you
              return (
                <li key={seat.player_id}
                  className="table-seat min-w-0 rounded-lg border p-3"
                  data-active={game.turn === seat.player_id}>
                  <p className="break-words text-sm text-club-ink">
                    <span className="seat-avatar" aria-hidden="true">♠</span>
                    {seat.nickname}{mine ? '（你）' : ''}
                    {seat.button ? ' ・莊' : ''}{seat.small_blind ? ' ・小盲' : ''}{seat.big_blind ? ' ・大盲' : ''}
                  </p>
                  <p className="text-xs text-club-muted">
                    籌碼 {seat.stack}・本輪下注 {seat.street_committed}
                    {seat.folded ? '・已棄牌' : ''}{seat.all_in ? '・全下' : ''}
                    {game.settled && seat.payout > 0 ? `・贏得 ${seat.payout}` : ''}
                  </p>
                  <div className="mt-2 flex gap-1">
                    {seat.folded && !mine ? null : (seat.cards ?? [null, null]).map((code, index) => (
                      <CardFace key={`${seat.player_id}-${String(index)}`} code={code} />
                    ))}
                  </div>
                </li>
              )
            })}
          </ul>
          <Controls key={game.state_version} game={game} send={send} />
          {game.over && view.summary.length > 0 && (
            <ul className="text-sm text-club-accent" aria-label="本手結果">
              {view.summary.map((entry) => (
                <li key={entry.nickname}>{entry.nickname}：{entry.net >= 0 ? '+' : ''}{entry.net}（現有 {entry.stack}）</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {canStart && (
        <button className="rounded-md border border-club-accent px-6 py-3 text-club-accent"
          onClick={() => { send({ type: 'start' }) }}>{game === null ? '開始牌局' : '下一手'}</button>
      )}
      {!view.is_host && (game === null || game.over) && <p className="text-sm text-club-muted">等待房主開始下一手…</p>}
      {view.is_host && active < 2 && game?.over === true && <p className="text-sm text-club-muted">只剩一位玩家有籌碼，遊戲結束。</p>}
    </div>
  )
}

export function Game({ onLeave }: { onLeave: () => void }) {
  const [session, setSession] = useState<Session | null>(loadSession)
  const [view, setView] = useState<View | null>(null)
  const [status, setStatus] = useState<'connecting' | 'open' | 'closed'>('connecting')
  const [notice, setNotice] = useState('')
  const [attempt, setAttempt] = useState(0)
  const socket = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (session === null) return undefined
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${scheme}://${window.location.host}/api/proto/rooms/${session.room}/ws`)
    socket.current = ws
    ws.onopen = () => { ws.send(JSON.stringify({ token: session.token })); setStatus('open') }
    ws.onmessage = (event: MessageEvent<string>) => {
      const data: unknown = JSON.parse(event.data)
      if (typeof data !== 'object' || data === null || !('type' in data)) return
      if (data.type === 'view') { setView(data as View); setNotice('') }
      if (data.type === 'error') {
        const problem = data as ServerError
        setNotice(errorMessage(problem.code, problem.message))
      }
    }
    ws.onclose = (event) => {
      setStatus('closed')
      if (event.code === 4401) { saveSession(null); setSession(null); setView(null) }
    }
    return () => { ws.onclose = null; ws.close() }
  }, [session, attempt])

  function send(message: object) {
    if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify(message))
  }
  function leave() {
    saveSession(null)
    setSession(null)
    setView(null)
    onLeave()
  }

  if (session === null) {
    return <RoomEntry onBack={onLeave} onJoined={(next) => { saveSession(next); setStatus('connecting'); setSession(next) }} />
  }
  return (
    <section className="space-y-4">
      {status === 'closed' && (
        <p role="alert" className="text-sm text-club-error">連線中斷。
          <button className="ml-2 underline" onClick={() => { setStatus('connecting'); setAttempt((n) => n + 1) }}>重新連線</button>
        </p>
      )}
      <p role="status" aria-live="polite" className="min-h-6 text-sm text-club-error">{notice}</p>
      {view === null ? <p className="text-club-muted">連線中…</p> : <Table view={view} send={send} />}
      <button className="text-xs text-club-muted underline" onClick={leave}>離開房間</button>
    </section>
  )
}
