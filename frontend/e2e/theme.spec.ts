import { expect, test, type Page } from '@playwright/test'

const themes = ['emerald', 'royal', 'garden', 'neon'] as const

async function openAppearance(page: Page) {
  await page.getByRole('button', { name: '外觀設定', exact: true }).click()
  return page.getByRole('dialog', { name: '外觀設定' })
}

async function enterPrototype(page: Page, nickname: string) {
  await page.goto('/')
  await page.getByRole('article', { name: '德州撲克', exact: true }).getByRole('button', { name: '建立或加入房間' }).click()
  await page.getByRole('textbox', { name: '暱稱' }).fill(nickname)
}

test('appearance previews, cancels with Escape, persists and resets', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  const scope = page.locator('.club-theme')
  await expect(scope).toHaveAttribute('data-theme', 'emerald')
  await expect(page.locator('.table-scene')).toHaveCSS('animation-name', 'none')
  const panel = await openAppearance(page)
  await expect(panel.getByRole('checkbox', { name: '套用確認音效' })).not.toBeChecked()
  await panel.getByRole('radio', { name: /Royal Black Gold/ }).check()
  await expect(scope).toHaveAttribute('data-theme', 'royal')
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()
  await expect(page.getByRole('button', { name: '外觀設定', exact: true })).toBeFocused()
  await expect(scope).toHaveAttribute('data-theme', 'emerald')

  await openAppearance(page)
  await panel.getByRole('radio', { name: /Art Nouveau Garden/ }).check()
  await panel.getByRole('combobox', { name: '牌背' }).selectOption('neon')
  await panel.getByRole('checkbox', { name: '減少動態效果' }).check()
  await panel.getByRole('button', { name: '套用', exact: true }).click()
  await page.reload()
  await expect(scope).toHaveAttribute('data-theme', 'garden')
  await expect(scope).toHaveAttribute('data-card-back', 'neon')
  await expect(scope).toHaveAttribute('data-motion', 'reduced')

  await openAppearance(page)
  await panel.getByRole('button', { name: '重設預設' }).click()
  await expect(scope).toHaveAttribute('data-theme', 'emerald')
  await panel.getByRole('button', { name: '取消', exact: true }).click()
  await expect(scope).toHaveAttribute('data-theme', 'garden')
  await openAppearance(page)
  await panel.getByRole('button', { name: '重設預設' }).click()
  await panel.getByRole('button', { name: '套用', exact: true }).click()
  await page.reload()
  await expect(scope).toHaveAttribute('data-theme', 'emerald')
  await expect(scope).toHaveAttribute('data-card-back', 'emerald')
  await expect(scope).toHaveAttribute('data-motion', 'system')
})

test('an unavailable storage keeps the applied theme for the current page', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', {
      get() { throw new DOMException('Storage blocked', 'SecurityError') },
    })
  })
  await page.goto('/')
  const scope = page.locator('.club-theme')
  await expect(scope).toHaveAttribute('data-theme', 'emerald')
  const panel = await openAppearance(page)
  await panel.getByRole('radio', { name: /Neon Night City/ }).check()
  await panel.getByRole('button', { name: '套用', exact: true }).click()
  await expect(scope).toHaveAttribute('data-theme', 'neon')
  await expect(page.getByText('外觀已套用於本頁，瀏覽器目前無法儲存。')).toBeVisible()
  await page.reload()
  await expect(scope).toHaveAttribute('data-theme', 'emerald')
})

test('live Texas table switches all themes and completes a hand', async ({ page, browser, baseURL }, info) => {
  test.skip(process.env.PROTOTYPE_ENABLED !== 'true', 'Run with PROTOTYPE_ENABLED=true to exercise the prototype')
  const guestContext = await browser.newContext({ baseURL })
  try {
    const guest = await guestContext.newPage()
    await enterPrototype(page, '青禾')
    await page.getByRole('button', { name: '建立房間' }).click()
    const room = page.locator('strong').filter({ hasText: /^[A-Z2-9]{5}$/ })
    await expect(room).toBeVisible()
    await enterPrototype(guest, '明川')
    await guest.getByRole('textbox', { name: '房間代碼' }).fill(await room.innerText())
    await guest.getByRole('button', { name: '加入', exact: true }).click()
    await page.getByRole('button', { name: '開始牌局' }).click()
    await expect(page.getByRole('img', { name: '暗牌' })).toHaveCount(2)
    await expect(guest.getByRole('img', { name: '暗牌' })).toHaveCount(2)
    await page.getByRole('button', { name: '跟注', exact: true }).click()
    await guest.getByRole('button', { name: '過牌', exact: true }).click()

    const table = page.locator('.live-table')
    const backgrounds = new Set<string>()
    for (const theme of themes) {
      const panel = await openAppearance(page)
      await panel.locator(`input[value="${theme}"]`).check()
      await expect(panel.locator('.appearance-preview .card')).toHaveCount(3)
      await panel.getByRole('button', { name: '套用', exact: true }).click()
      await expect(page.getByRole('group', { name: '公共牌' }).getByRole('img')).toHaveCount(3)
      await expect(page.getByRole('img', { name: '暗牌' })).toHaveCount(2)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
        await page.evaluate(() => window.innerWidth),
      )
      backgrounds.add(await table.evaluate((element) => getComputedStyle(element).backgroundImage))
      const screenshot = info.outputPath(`${theme}.png`)
      await page.screenshot({ path: screenshot, fullPage: true, animations: 'disabled' })
      await info.attach(`${theme} live table`, { path: screenshot, contentType: 'image/png' })
    }
    expect(backgrounds.size).toBe(4)
    for (let street = 0; street < 3; street += 1) {
      await guest.getByRole('button', { name: '過牌', exact: true }).click()
      await page.getByRole('button', { name: '過牌', exact: true }).click()
    }
    await expect(page.getByRole('group', { name: '公共牌' }).getByRole('img')).toHaveCount(5)
    await expect(page.getByRole('list', { name: '本手結果' })).toBeVisible()
    await expect(guest.getByRole('list', { name: '本手結果' })).toBeVisible()
    await page.getByRole('button', { name: '下一手' }).click()
    await expect(page.getByText(/第 2 手/)).toBeVisible()
  } finally {
    await guestContext.close()
  }
})
