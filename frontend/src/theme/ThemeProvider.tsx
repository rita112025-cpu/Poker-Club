import { useRef, useState, type ReactNode } from 'react'
import { defaults, presets, readPreferences, writePreferences, type Preferences, type Preset } from './preferences'

export function ThemeProvider({ children }: { children: (settings: ReactNode) => ReactNode }) {
  const [saved, setSaved] = useState(() => readPreferences(() => window.localStorage))
  const [draft, setDraft] = useState<Preferences | null>(null)
  const [notice, setNotice] = useState('')
  const dialog = useRef<HTMLDialogElement>(null)
  const appearance = draft ?? saved

  function open() {
    setDraft(saved)
    dialog.current?.showModal()
  }

  function apply() {
    setSaved(appearance)
    const persisted = writePreferences(() => window.localStorage, appearance)
    setNotice(persisted ? '' : '外觀已套用於本頁，瀏覽器目前無法儲存。')
    dialog.current?.close()
    if (appearance.sound && typeof AudioContext !== 'undefined') {
      try {
        const audio = new AudioContext()
        const tone = audio.createOscillator()
        const volume = audio.createGain()
        tone.frequency.value = 523.25
        volume.gain.setValueAtTime(0.06, audio.currentTime)
        volume.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.14)
        tone.connect(volume).connect(audio.destination)
        tone.onended = () => { void audio.close().catch(() => undefined) }
        tone.start()
        tone.stop(audio.currentTime + 0.14)
      } catch { /* Appearance stays applied when audio is unavailable. */ }
    }
  }

  return (
    <div className="club-theme" data-theme={appearance.preset}
      data-card-back={appearance.back === 'matching' ? appearance.preset : appearance.back}
      data-motion={appearance.motion}>
      {children(<button type="button" className="settings-trigger" onClick={open}>外觀設定</button>)}
      {notice && <p className="appearance-notice" role="status">{notice}</p>}
      <dialog ref={dialog} className="appearance-dialog" aria-labelledby="appearance-title"
        onClose={() => { setDraft(null) }}
        onCancel={(event) => { event.preventDefault(); setDraft(null); dialog.current?.close() }}>
        <div className="appearance-heading">
          <h2 id="appearance-title">外觀設定</h2>
          <button type="button" className="settings-trigger" aria-label="取消外觀設定"
            onClick={() => { setDraft(null); dialog.current?.close() }}>關閉</button>
        </div>
        <div className="appearance-preview" aria-hidden="true">
          <span className="preview-avatar">♠</span>
          <span className="card card-black">A♠</span>
          <span className="card card-red">Q♥</span>
          <span className="card card-down" />
          <span className="preview-chip" />
        </div>
        <fieldset className="preset-list">
          <legend>牌桌主題</legend>
          {(Object.keys(presets) as Preset[]).map((preset) => (
            <label key={preset}>
              <input type="radio" name="table-theme" value={preset} checked={appearance.preset === preset}
                onChange={() => { setDraft({ ...appearance, preset }) }} />
              {presets[preset]}
            </label>
          ))}
        </fieldset>
        <label className="appearance-option">牌背
          <select value={appearance.back}
            onChange={(event) => { setDraft({ ...appearance, back: event.target.value as Preferences['back'] }) }}>
            <option value="matching">跟隨主題</option>
            {Object.entries(presets).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </label>
        <label className="appearance-option"><input type="checkbox" checked={appearance.motion === 'reduced'}
          onChange={(event) => { setDraft({ ...appearance, motion: event.target.checked ? 'reduced' : 'system' }) }} />
          減少動態效果
        </label>
        <label className="appearance-option"><input type="checkbox" checked={appearance.sound}
          onChange={(event) => { setDraft({ ...appearance, sound: event.target.checked }) }} />套用確認音效
        </label>
        <div className="appearance-actions">
          <button type="button" className="settings-trigger" onClick={() => { setDraft(defaults) }}>重設預設</button>
          <button type="button" className="settings-trigger"
            onClick={() => { setDraft(null); dialog.current?.close() }}>取消</button>
          <button type="button" className="settings-trigger appearance-apply" onClick={apply}>套用</button>
        </div>
      </dialog>
    </div>
  )
}
