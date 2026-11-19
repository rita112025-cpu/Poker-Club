import { useEffect, useRef, useState } from 'react'
import { CardFace, RoomEntry } from '../../Game'
import './big-two.css'

type Session = { room: string; token: string }
type Member = { id: string; name: string; connected: boolean; points: number }
type Hand = {
  game_id: string; state_version: number; turn: string | null; target: string[]
  hand: string[]; counts: Record<string, number>; opening: boolean; passes: number
  result: { id: string; delta: number; rank: number }[] | null
}
type View = {
  type: 'view'; room: string; you: string; is_host: boolean; members: Member[]; game: Hand | null
}
type Action = {
  type: 'action'; game_id: string; request_id: string; state_version: number
  action: { type: 'pass' } | { type: 'play'; cards: string[] }
}
type Receipt = {
  type: 'receipt'; request_id: string; accepted: boolean; code?: string; message?: string
}
type ServerError = { type: 'error'; code: string; message?: string }

const STORAGE_KEY = 'poker-big-two-proto-session'
const errors: Record<string, string> = {
  four_players_required: '四位玩家都在線後才能開局。',
  not_host: '只有房主可以開局。',
  game_in_progress: '此局仍在進行。',
  stale_state: '牌局已更新，請重新選牌。',
  game_mismatch: '這個動作屬於另一局。',
  bad_message: '無法處理這個動作。',
}

function createRequestId() {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // randomUUID requires a secure context. Private LAN play can use plain HTTP.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-')
}

function loadSession(): Session | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? 'null')
    if (typeof value === 'object' && value !== null && 'room' in value && 'token' in value &&
      typeof value.room === 'string' && typeof value.token === 'string') {
      return { room: value.room, token: value.token }
    }
  } catch { /* The room may still be used without storage. */ }
  return null
}

function saveSession(session: Session | null) {
  try {
    if (session === null) sessionStorage.removeItem(STORAGE_KEY)
    else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch { /* The room may still be used without storage. */ }
}

function HandControls({ game, ready, onAction }: {
  game: Hand; ready: boolean; onAction: (action: Action['action']) => void
}) {
  const [selected, setSelected] = useState<string[]>([])
  return (
    <>
      <div className="flex flex-wrap gap-2" role="group" aria-label="我的手牌">
        {game.hand.map((code) => (
          <button key={code} type="button" aria-label={`選牌 ${code}`} aria-pressed={selected.includes(code)}
            className="rounded border-2 border-transparent aria-pressed:border-club-accent"
            disabled={!ready} onClick={() => {
              setSelected((cards) => cards.includes(code)
                ? cards.filter((card) => card !== code) : [...cards, code])
            }}><CardFace code={code} /></button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="settings-trigger" type="button" disabled={!ready || selected.length === 0}
          onClick={() => { onAction({ type: 'play', cards: selected }) }}>出牌</button>
        <button className="settings-trigger" type="button" disabled={!ready || game.target.length === 0}
          onClick={() => { onAction({ type: 'pass' }) }}>過牌</button>
      </div>
    </>
  )
}

export function BigTwoGame({ onLeave }: { onLeave: () => void }) {
  const [session, setSession] = useState(loadSession)
  const [view, setView] = useState<View | null>(null)
  const [connected, setConnected] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [notice, setNotice] = useState('')
  const [waiting, setWaiting] = useState(false)
  const pending = useRef<Action | null>(null)
  const socket = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (session === null) return
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${scheme}://${window.location.host}/api/proto/big-two/rooms/${encodeURIComponent(session.room)}/ws`)
    socket.current = ws
    let firstView = true
    let latest: Hand | null = null

    function clearPending() {
      pending.current = null
      setWaiting(false)
    }

    ws.onopen = () => { ws.send(JSON.stringify({ token: session.token })) }
    ws.onmessage = (event: MessageEvent<string>) => {
      let message: View | Receipt | ServerError
      try { message = JSON.parse(event.data) as typeof message } catch { return }
      if (!message || typeof message !== 'object') return
      if (message.type === 'view') {
        latest = message.game
        setView(message)
        setConnected(true)
        const action = pending.current
        if (action && firstView) {
          ws.send(JSON.stringify(action))
        } else if (action && (latest?.game_id !== action.game_id || latest.state_version > action.state_version)) {
          clearPending()
        }
        firstView = false
      } else if (message.type === 'receipt' && message.request_id === pending.current?.request_id) {
        if (!message.accepted) {
          setNotice(message.message ?? errors[message.code ?? ''] ?? '動作未完成。')
          clearPending()
        } else if (latest?.game_id !== pending.current.game_id ||
          latest.state_version > pending.current.state_version) {
          clearPending()
        }
      } else if (message.type === 'error') {
        setNotice(message.message ?? errors[message.code] ?? '動作未完成。')
        clearPending()
      }
    }
    ws.onclose = (event) => {
      setConnected(false)
      if (event.code === 4401 || event.code === 4001) {
        saveSession(null)
        setSession(null)
        setView(null)
        clearPending()
        setNotice('房間已關閉、到期或憑證無效。')
      } else {
        setNotice('連線中斷，請重新連線。')
      }
    }
    return () => {
      ws.onopen = ws.onmessage = ws.onclose = null
      ws.close()
    }
  }, [session, attempt])

  function submit(action: Action['action']) {
    const game = view?.game
    const ws = socket.current
    if (!game || !connected || ws?.readyState !== WebSocket.OPEN || pending.current) return
    const request: Action = {
      type: 'action', game_id: game.game_id, request_id: createRequestId(),
      state_version: game.state_version, action,
    }
    pending.current = request
    setWaiting(true)
    setNotice('')
    ws.send(JSON.stringify(request))
  }

  function send(type: 'start' | 'close_room') {
    const ws = socket.current
    if (connected && ws?.readyState === WebSocket.OPEN) {
      setNotice('')
      ws.send(JSON.stringify({ type }))
    }
  }

  if (session === null) return (
    <>
      {notice && <p role="alert">{notice}</p>}
      <RoomEntry bigTwo onBack={onLeave} onJoined={(next) => {
        saveSession(next)
        setNotice('')
        setSession(next)
      }} />
    </>
  )

  const game = view?.game
  const actor = view?.members.find((member) => member.id === game?.turn)
  const winner = view?.members.find((member) => member.id === game?.result?.find((row) => row.rank === 1)?.id)
  const myTurn = game?.turn === view?.you
  return (
    <section className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-2xl font-bold">大老二</h1>
      <p>房間代碼 <strong>{session.room}</strong></p>
      <p role="status">{notice || (waiting ? '等待伺服器回覆…' : !connected ? '等待連線…' : '')}</p>
      {!connected && (
        <button className="settings-trigger" type="button" onClick={() => {
          setNotice('')
          setAttempt((value) => value + 1)
        }}>重新連線</button>
      )}
      {view && (
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="玩家">
          {view.members.map((member) => (
            <li key={member.id} className="table-seat min-w-0 rounded border p-2 break-words"
              data-active={member.id === game?.turn}>
              {member.name}{member.id === view.you && '（你）'}<br />
              {member.connected ? '在線' : '離線'} · {member.points} 分
              {game && <span className="block">剩餘 {game.counts[member.id]} 張</span>}
            </li>
          ))}
        </ul>
      )}
      {game && (
        <div className="live-table space-y-4 rounded-xl border p-4">
          <p aria-live="polite">{winner ? `勝者：${winner.name}` : myTurn
            ? (game.opening ? '輪到你，首組須包含梅花 3' : '輪到你')
            : `等待 ${actor?.name ?? '玩家'}${actor && !actor.connected ? ' 重連' : ' 出牌'}`}</p>
          <div key={game.target.join()} className="big-two-play flex flex-wrap gap-2" role="group" aria-label="待壓牌組">
            {game.target.length ? game.target.map((code) => <CardFace key={code} code={code} />)
              : '目前可自由領出'}
          </div>
          {game.passes > 0 && <p>連續過牌 {game.passes} 次</p>}
          <HandControls key={`${game.game_id}:${game.state_version}`} game={game}
            ready={Boolean(myTurn && connected && !waiting)} onAction={submit} />
          {game.result && <ul aria-label="本局結算">{game.result.map((row) => (
            <li key={row.id}>第 {row.rank} 名 · {view?.members.find((member) => member.id === row.id)?.name} · {row.delta > 0 ? '+' : ''}{row.delta}</li>
          ))}</ul>}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {view?.is_host && (!game || game.result) && <button className="settings-trigger" type="button"
          disabled={!connected || view.members.length !== 4 || view.members.some((member) => !member.connected)}
          onClick={() => { send('start') }}>{game ? '下一局' : '開始大老二'}</button>}
        {view?.is_host && <button className="settings-trigger" type="button" disabled={!connected}
          onClick={() => { if (window.confirm('關閉房間並清除房內積分？')) send('close_room') }}>關閉房間</button>}
        <button className="settings-trigger" type="button" onClick={onLeave}>離開房間</button>
      </div>
    </section>
  )
}
