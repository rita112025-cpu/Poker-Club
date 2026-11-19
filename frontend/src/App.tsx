import { useState, type ReactNode } from 'react'
import { ThemeProvider } from './theme/ThemeProvider'
import { Game } from './Game'
import { BigTwoGame } from './games/big_two/BigTwoGame'
import { ClubLobby, type PlayableGame } from './lobby/ClubLobby'

type Health = 'idle' | 'checking' | 'online' | 'offline'

export function App() {
  return <ThemeProvider>{(settings) => <Club settings={settings} />}</ThemeProvider>
}

function Club({ settings }: { settings: ReactNode }) {
  const [health, setHealth] = useState<Health>('idle')
  const [playing, setPlaying] = useState<PlayableGame | null>(null)

  async function checkConnection() {
    setHealth('checking')
    try {
      const response = await fetch('/api/health/live', { signal: AbortSignal.timeout(5000) })
      const body: unknown = await response.json()
      if (!response.ok || typeof body !== 'object' || body === null ||
        !('status' in body) || body.status !== 'ok') throw new Error('Unavailable')
      setHealth('online')
    } catch {
      setHealth('offline')
    }
  }

  const statusText: Record<Health, string> = {
    idle: '尚未檢查 API 連線', checking: '正在連線…',
    online: 'API 連線正常（不代表資料庫或多人遊戲已就緒）',
    offline: '無法連線至 API，請確認後端已啟動後重試。',
  }

  return (
    <div className="min-h-screen px-5 py-7 text-club-ink sm:px-12">
      <header className="mx-auto flex max-w-6xl items-center justify-between gap-4 border-b border-club-line pb-6">
        <a className="brand" href="/" aria-label="Poker Club 首頁">♠ <span>POKER CLUB</span></a>
        {settings}
      </header>
      {playing && <main className="mx-auto max-w-6xl py-10">
        {playing === 'texas' ? <Game onLeave={() => { setPlaying(null) }} /> :
          <BigTwoGame onLeave={() => { setPlaying(null) }} />}
      </main>}
      {!playing && <main className="mx-auto max-w-6xl">
        <div className="grid gap-12 py-16 lg:grid-cols-2 lg:items-center lg:py-20">
          <section>
            <p className="mb-6 text-xs tracking-[0.3em] text-club-accent">THE TABLE IS YOURS</p>
            <h1 className="text-4xl font-semibold leading-tight sm:text-6xl">好牌，好朋友。<br /><span className="text-club-accent">相聚同一桌。</span></h1>
            <p className="mt-7 max-w-md leading-8 text-club-muted">查看遊戲規則、支援人數和試玩狀態。</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a className="settings-trigger lobby-link lobby-entry" href="#game-lobby">瀏覽遊戲</a>
              <button className="settings-trigger" disabled={health === 'checking'}
                onClick={() => { void checkConnection() }}>
                {health === 'checking' ? '檢查中…' : '檢查 API 連線'}
              </button>
            </div>
            <p role="status" aria-live="polite" className="mt-4 min-h-12 text-sm leading-6 text-club-muted">{statusText[health]}</p>
          </section>
          <div aria-hidden="true" className="table-scene">
            <div className="felt-table">
              <span className="table-wordmark">POKER CLUB</span>
              <div className="playing-card card-back">♠</div>
              <div className="playing-card card-front"><span>A<br />♠</span><strong>♠</strong><span className="card-bottom">A<br />♠</span></div>
              <div className="chip chip-one" /><div className="chip chip-two" /><div className="chip chip-three" />
            </div>
            <p className="mt-5 text-center text-xs tracking-widest text-club-muted">牌桌視覺示意・非進行中的牌局</p>
          </div>
        </div>
        <ClubLobby onPlay={(game) => { setPlaying(game); window.scrollTo(0, 0) }} />
      </main>}
      <footer className="mx-auto max-w-6xl border-t border-club-line pt-6 text-xs leading-6 text-club-muted">POKER CLUB · 僅供休閒娛樂 · 不提供現金下注、兌換或交易</footer>
    </div>
  )
}
