import assert from 'node:assert/strict'
import test from 'node:test'
import { defaults, readPreferences, storageKey, writePreferences } from '../src/theme/preferences.ts'

test('missing, invalid, and unsupported versions use defaults', () => {
  for (const raw of [null, '{', 'null', '{"version":2,"preset":"neon"}']) {
    assert.deepEqual(readPreferences(() => ({ getItem: () => raw })), defaults)
  }
})

test('valid fields survive invalid fields and inherited preset names are rejected', () => {
  const raw = '{"version":1,"preset":"constructor","back":"royal","motion":"invalid","sound":true}'
  assert.deepEqual(readPreferences(() => ({ getItem: () => raw })), {
    ...defaults, back: 'royal', sound: true,
  })
})

test('writes versioned settings and reads them on reload', () => {
  const storage = new Map()
  const settings = { ...defaults, preset: 'garden', motion: 'reduced' }
  assert.equal(writePreferences(() => ({ setItem: storage.set.bind(storage) }), settings), true)
  assert.equal(JSON.parse(storage.get(storageKey)).version, 1)
  assert.deepEqual(readPreferences(() => ({ getItem: storage.get.bind(storage) })), settings)
})

test('storage errors fall back safely on both reads and writes', () => {
  const blocked = () => { throw new Error('Storage blocked') }
  assert.deepEqual(readPreferences(blocked), defaults)
  assert.equal(writePreferences(blocked, defaults), false)
  assert.equal(writePreferences(() => ({ setItem: blocked }), defaults), false)
})
