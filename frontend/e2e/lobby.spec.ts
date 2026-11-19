import { expect, test } from '@playwright/test'

test('the catalog shows four games and only links to the enabled prototype', async ({ page }, info) => {
  await page.goto('/')
  const lobby = page.getByRole('region', { name: '遊戲大廳' })
  await expect(lobby.getByRole('article')).toHaveCount(4)
  const planned = ['十三支', '五張抽牌']
  if (process.env.BIG_TWO_PROTOTYPE_ENABLED !== 'true') planned.push('大老二')
  for (const name of planned) {
    const card = lobby.getByRole('article', { name, exact: true })
    await expect(card.getByText('開發中')).toBeVisible()
    await expect(card.getByRole('button').or(card.getByRole('link'))).toHaveCount(0)
  }
  const texas = lobby.getByRole('article', { name: '德州撲克', exact: true })
  const entry = texas.getByRole('button', { name: '建立或加入房間' })
  if (process.env.PROTOTYPE_ENABLED === 'true') {
    await expect(texas.getByText('私人試玩')).toBeVisible()
    await entry.click()
    await expect(page.getByRole('button', { name: '建立房間' })).toBeVisible()
    await page.getByRole('textbox', { name: '暱稱' }).fill('測試玩家')
    await page.getByRole('textbox', { name: '房間代碼' }).fill('00000')
    await page.getByRole('button', { name: '加入', exact: true }).click()
    await expect(page.getByText('找不到這個房間')).toBeVisible()
    await page.getByRole('button', { name: '返回遊戲大廳' }).click()
    await expect(entry).toBeVisible()
  } else {
    await expect(texas.getByText('試玩未開放')).toBeVisible()
    await expect(entry).toHaveCount(0)
  }

  await page.getByRole('button', { name: '外觀設定', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const preview = lobby.locator('.lobby-preview').first()
  const initial = await preview.evaluate((element) => getComputedStyle(element).backgroundImage)
  await dialog.getByRole('radio', { name: /Neon Night City/ }).check()
  await expect.poll(() => preview.evaluate((element) => getComputedStyle(element).backgroundImage))
    .not.toBe(initial)
  await dialog.getByRole('button', { name: '套用', exact: true }).click()
  await expect(lobby).toBeVisible()
  const primaryActions = [page.getByRole('link', { name: '瀏覽遊戲' })]
  if (process.env.PROTOTYPE_ENABLED === 'true') primaryActions.push(entry)
  for (const action of primaryActions) {
    const { foreground, background } = await action.evaluate((element) => {
      const style = getComputedStyle(element)
      return { foreground: style.color, background: style.backgroundColor }
    })
    expect(foreground).not.toBe(background)
  }
  await page.screenshot({ path: info.outputPath('lobby.png'), fullPage: true, animations: 'disabled' })
})

test('lobby fits phone, tablet and desktop widths', async ({ page }, info) => {
  await page.goto('/')
  const grid = page.locator('.lobby-grid')
  for (const [width, expectedColumns] of [[320, 1], [768, 2], [1280, 4]]) {
    await page.setViewportSize({ width, height: 900 })
    await expect.poll(() => grid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length))
      .toBe(expectedColumns)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    if (width === 768 && info.project.name === 'desktop-chromium') {
      await page.screenshot({ path: info.outputPath('tablet-lobby.png'), fullPage: true, animations: 'disabled' })
    }
  }
})

test('a failed availability check hides entry and can be retried', async ({ page }) => {
  await page.route('**/api/proto/status', (route) => route.abort('failed'))
  await page.goto('/')
  const texas = page.getByRole('article', { name: '德州撲克', exact: true })
  await expect(texas.getByText('無法確認試玩狀態')).toBeVisible()
  await expect(texas.getByRole('button', { name: '建立或加入房間' })).toHaveCount(0)
  await page.unroute('**/api/proto/status')
  await texas.getByRole('button', { name: '重新確認試玩狀態' }).click()
  await expect(texas.getByText(process.env.PROTOTYPE_ENABLED === 'true' ? '私人試玩' : '試玩未開放')).toBeVisible()
})

test('the status check times out and retries without AbortSignal.any', async ({ page }) => {
  await page.addInitScript(() => { Reflect.deleteProperty(AbortSignal, 'any') })
  await page.clock.install()
  let release = () => {}
  const pending = new Promise<void>((resolve) => { release = resolve })
  try {
    await page.route('**/api/proto/status', async () => { await pending })
    const request = page.waitForRequest('**/api/proto/status')
    await page.goto('/')
    await request
    await page.clock.fastForward(5100)
    const texas = page.getByRole('article', { name: '德州撲克', exact: true })
    await expect(texas.getByText('無法確認試玩狀態')).toBeVisible()
    await expect(texas.getByRole('button', { name: '建立或加入房間' })).toHaveCount(0)
    await page.unroute('**/api/proto/status')
    await texas.getByRole('button', { name: '重新確認試玩狀態' }).click()
    await expect(texas.getByText(process.env.PROTOTYPE_ENABLED === 'true' ? '私人試玩' : '試玩未開放')).toBeVisible()
  } finally {
    release()
  }
})

for (const action of ['建立房間', '加入'] as const) {
  test(`room entry keeps the user on the form while waiting to ${action}`, async ({ page, request }) => {
    test.skip(process.env.PROTOTYPE_ENABLED !== 'true', 'Requires the prototype room routes')
    const create = action === '建立房間'
    let room = ''
    if (!create) {
      const response = await request.post('/api/proto/rooms', { data: { nickname: '房主' } })
      expect(response.ok()).toBe(true)
      const body = await response.json() as { room: string }
      room = body.room
    }

    const path = create ? '/api/proto/rooms' : `/api/proto/rooms/${room}/join`
    let release = () => {}
    const pending = new Promise<void>((resolve) => { release = resolve })
    await page.route(`**${path}`, async (route) => {
      await pending
      await route.continue()
    })

    try {
      await page.goto('/')
      await page.getByRole('article', { name: '德州撲克', exact: true }).getByRole('button', { name: '建立或加入房間' }).click()
      await page.getByRole('textbox', { name: '暱稱' }).fill('等待測試')
      if (!create) await page.getByRole('textbox', { name: '房間代碼' }).fill(room)
      await page.getByRole('button', { name: action, exact: true }).click()
      await expect(page.getByRole('button', { name: '返回遊戲大廳' })).toBeDisabled()
      await expect(page.getByRole('status')).toContainText('房間請求處理中')
      release()
      await expect(page.getByText(/房間代碼/)).toBeVisible()
      await expect(page.getByRole('button', { name: '離開房間' })).toBeVisible()
    } finally {
      release()
    }
  })
}
