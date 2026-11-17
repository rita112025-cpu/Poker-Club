import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Game } from './Game'

type Health = 'idle' | 'checking' | 'online' | 'offline'

export function App() {
  const [health, setHealth] = useState<Health>('idle')
  const reduceMotion = useReducedMotion()
  const [playing, setPlaying] = useState(false)

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
    <div className="min-h-screen px-5 py-7 text-stone-100 sm:px-12">
      <header className="mx-auto flex max-w-6xl items-center justify-between gap-4 border-b border-white/10 pb-6">
        <a className="brand" href="/" aria-label="Poker Club 首頁">♠ <span>POKER CLUB</span></a>
        <span className="text-xs tracking-widest text-amber-200/80">私人牌桌・好友相聚</span>
      </header>
      {playing && <main className="mx-auto max-w-6xl py-10"><Game onLeave={() => { setPlaying(false) }} /></main>}
      {!playing && <main className="mx-auto grid max-w-6xl gap-12 py-16 lg:grid-cols-2 lg:items-center lg:py-28">
        <section>
          <p className="mb-6 text-xs tracking-[0.3em] text-amber-200">THE TABLE IS YOURS</p>
          <h1 className="text-4xl font-semibold leading-tight sm:text-6xl">好牌，好朋友。<br /><span className="text-amber-200">相聚同一桌。</span></h1>
          <p className="mt-7 max-w-md leading-8 text-stone-400">專屬於你們的撲克牌聚會空間。德州撲克與大老二，將從這裡開始。</p>
          <div className="mt-9 border-l-2 border-amber-200/60 pl-5">
            <h2 className="font-medium text-amber-100">Phase 1｜基礎建設</h2>
            <p className="mt-2 text-sm leading-7 text-stone-400">目前尚未開放登入、建立房間及遊戲。<br />所有遊戲積分均無現金價值。</p>
          </div>
          <button className="mt-8 rounded-md border border-amber-200/60 px-6 py-3 text-sm text-amber-100 transition hover:bg-amber-200/10 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-amber-200 disabled:opacity-50"
            disabled={health === 'checking'} onClick={() => { void checkConnection() }}>
            {health === 'checking' ? '檢查中…' : '檢查 API 連線'}
          </button>
          <button className="ml-3 mt-8 rounded-md border border-emerald-300/60 px-6 py-3 text-sm text-emerald-100 transition hover:bg-emerald-300/10"
            onClick={() => { setPlaying(true) }}>開始試玩（原型）</button>
          <p role="status" aria-live="polite" className="mt-4 min-h-12 text-sm leading-6 text-stone-400">{statusText[health]}</p>
        </section>
        <motion.div aria-hidden="true" className="table-scene" initial={reduceMotion ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          <div className="felt-table">
            <span className="table-wordmark">POKER CLUB</span>
            <div className="playing-card card-back">♠</div>
            <div className="playing-card card-front"><span>A<br />♠</span><strong>♠</strong><span className="card-bottom">A<br />♠</span></div>
            <div className="chip chip-one" /><div className="chip chip-two" /><div className="chip chip-three" />
          </div>
          <p className="mt-5 text-center text-xs tracking-widest text-stone-500">牌桌視覺示意・非進行中的牌局</p>
        </motion.div>
      </main>}
      <footer className="mx-auto max-w-6xl border-t border-white/10 pt-6 text-xs leading-6 text-stone-500">POKER CLUB · 僅供休閒娛樂 · 不提供現金下注、兌換或交易</footer>
    </div>
  )
}
