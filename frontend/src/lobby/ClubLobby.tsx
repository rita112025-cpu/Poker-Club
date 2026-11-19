import { useEffect, useState } from 'react'
import './lobby.css'

const games = [
  { id: 'texas', name: '德州撲克', english: "Texas Hold’em", players: '2–9 人',
    rules: '從兩張底牌與五張公共牌中選出最佳五張牌，透過多輪下注爭取底池。',
    cards: ['A♠', 'K♥', 'Q♠', 'J♣', '10♠'] },
  { id: 'big-two', name: '大老二', english: 'Big Two', players: '4 人（規劃）',
    rules: '每人 13 張牌，輪流打出更大的同張數組合。率先打完手牌即獲勝。',
    cards: ['3♦', '3♣', '3♥'] },
  { id: 'chinese', name: '十三支', english: 'Chinese Poker', players: '2–4 人（規劃）',
    rules: '將 13 張手牌排成前墩 3 張、中墩 5 張與後墩 5 張，再逐墩比牌。',
    cards: ['A♦', 'A♣', 'K♥'] },
  { id: 'draw', name: '五張抽牌', english: 'Five-Card Draw', players: '2–6 人（規劃）',
    rules: '每人持有五張牌，可保留或更換手牌，最後透過下注與攤牌決定勝負。',
    cards: ['9♣', '9♥', '9♠'] },
]

export type PlayableGame = 'texas' | 'big-two'

type Availability = 'checking' | 'available' | 'disabled' | 'unreachable'

const availabilityText: Record<Availability, string> = {
  checking: '確認試玩狀態中…',
  available: '私人試玩',
  disabled: '試玩未開放',
  unreachable: '無法確認試玩狀態',
}

function useAvailability(path: string) {
  const [availability, setAvailability] = useState<Availability>('checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const request = new AbortController()
    let active = true
    const timeout = window.setTimeout(() => { request.abort() }, 5000)
    async function check() {
      try {
        const response = await fetch(path, { signal: request.signal, cache: 'no-store' })
        if (!active) return
        if (response.status === 404) {
          setAvailability('disabled')
          return
        }
        if (!response.ok) throw new Error('Status unavailable')
        const body: unknown = await response.json()
        if (active) {
          setAvailability(typeof body === 'object' && body !== null &&
            'available' in body && body.available === true ? 'available' : 'unreachable')
        }
      } catch {
        if (active) setAvailability('unreachable')
      } finally {
        window.clearTimeout(timeout)
      }
    }
    void check()
    return () => {
      active = false
      window.clearTimeout(timeout)
      request.abort()
    }
  }, [attempt, path])

  return { availability, retry: () => {
    setAvailability('checking')
    setAttempt((previous) => previous + 1)
  } }
}

export function ClubLobby({ onPlay }: { onPlay: (game: PlayableGame) => void }) {
  const texas = useAvailability('/api/proto/status')
  const bigTwo = useAvailability('/api/proto/big-two/status')

  return (
    <section id="game-lobby" className="game-lobby" aria-labelledby="lobby-heading">
      <div className="lobby-heading">
        <h2 id="lobby-heading">遊戲大廳</h2>
        <p>選擇遊戲，或用房間代碼加入朋友的牌桌。</p>
      </div>
      <div className="lobby-grid">
        {games.map((game) => {
          const playable = game.id === 'texas' || game.id === 'big-two' ? game.id : null
          const status = playable === 'texas' ? texas : playable === 'big-two' ? bigTwo : null
          const available = status?.availability === 'available'
          return (
            <article key={game.id} className="lobby-card" aria-labelledby={`game-${game.id}`}>
              <div className={`lobby-preview lobby-preview-${game.id}`} aria-hidden="true">
                <div className="lobby-preview-felt" />
                <div className="lobby-preview-hand">
                  {game.cards.map((card) => (
                    <span key={card} className={`card ${/[♥♦]/u.test(card) ? 'card-red' : 'card-black'}`}>{card}</span>
                  ))}
                  {game.id === 'draw' && <span className="card card-down" />}
                </div>
              </div>
              <div className="lobby-card-body">
                <div className="lobby-card-heading">
                  <h3 id={`game-${game.id}`}>{game.name}</h3>
                  <span className="lobby-badge" data-available={available} aria-live={status ? 'polite' : undefined}>
                    {status && (game.id === 'texas' || status.availability !== 'disabled')
                      ? availabilityText[status.availability] : '開發中'}
                  </span>
                </div>
                <p className="lobby-meta" lang="en">{game.english}</p>
                <p className="lobby-rules">{game.rules}</p>
                <p className="lobby-players">{game.id === 'big-two' && available ? '4 人' : game.players}</p>
                {available && playable && (
                  <button className="settings-trigger lobby-entry" type="button"
                    onClick={() => { onPlay(playable) }}>建立或加入房間</button>
                )}
                {(status?.availability === 'unreachable' ||
                  (game.id === 'texas' && status?.availability === 'disabled')) && (
                  <button className="settings-trigger" type="button" onClick={status.retry}>重新確認試玩狀態</button>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
