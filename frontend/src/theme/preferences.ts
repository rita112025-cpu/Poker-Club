export const presets = {
  emerald: 'Classic Emerald｜經典綠絨',
  royal: 'Royal Black Gold｜皇家黑金',
  garden: 'Art Nouveau Garden｜新藝術花園',
  neon: 'Neon Night City｜霓虹夜城',
} as const

export type Preset = keyof typeof presets
export type Preferences = {
  preset: Preset
  back: Preset | 'matching'
  motion: 'system' | 'reduced'
  sound: boolean
}

export const storageKey = 'poker-club.appearance'
export const defaults: Preferences = {
  preset: 'emerald',
  back: 'matching',
  motion: 'system',
  sound: false,
}

function isPreset(value: unknown): value is Preset {
  return typeof value === 'string' && Object.hasOwn(presets, value)
}

export function readPreferences(storage: () => Pick<Storage, 'getItem'>): Preferences {
  try {
    const raw = storage().getItem(storageKey)
    if (raw === null) return defaults
    const value: unknown = JSON.parse(raw)
    if (typeof value !== 'object' || value === null || !('version' in value) || value.version !== 1) {
      return defaults
    }
    return {
      preset: 'preset' in value && isPreset(value.preset) ? value.preset : defaults.preset,
      back: 'back' in value && isPreset(value.back) ? value.back : defaults.back,
      motion: 'motion' in value && value.motion === 'reduced' ? 'reduced' : defaults.motion,
      sound: 'sound' in value && value.sound === true,
    }
  } catch {
    return defaults
  }
}

export function writePreferences(storage: () => Pick<Storage, 'setItem'>, preferences: Preferences) {
  try {
    storage().setItem(storageKey, JSON.stringify({ version: 1, ...preferences }))
    return true
  } catch {
    return false
  }
}
