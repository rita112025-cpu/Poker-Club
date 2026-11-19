import { expect, test, type Page } from '@playwright/test'

const ranks = '3 4 5 6 7 8 9 10 J Q K A 2'.split(' ')
function strength(code: string) {
  return ranks.indexOf(code.slice(0, -1)) * 4 + 'CDHS'.indexOf(code.slice(-1))
}

async function enter(page: Page) {
  await page.goto('/')
  await page.getByRole('article', { name: '大老二', exact: true })
    .getByRole('button', { name: '建立或加入房間' }).click()
}

test('Big Two availability follows its own server setting', async ({ page }) => {
  await page.goto('/')
  const card = page.getByRole('article', { name: '大老二', exact: true })
  const enabled = process.env.BIG_TWO_PROTOTYPE_ENABLED === 'true'
  await expect(card.getByText(enabled ? '私人試玩' : '開發中')).toBeVisible()
  await expect(card.getByRole('button', { name: '建立或加入房間' })).toHaveCount(enabled ? 1 : 0)
})

test('four browsers reconnect and finish a Big Two hand', async ({ page, browser, baseURL }, info) => {
  test.skip(process.env.BIG_TWO_PROTOTYPE_ENABLED !== 'true', 'Requires the Big Two prototype')
  test.setTimeout(120_000)
  const contexts = await Promise.all([1, 2, 3].map(() => browser.newContext({ baseURL })))
  try {
    const pages = [page, ...await Promise.all(contexts.map((context) => context.newPage()))]
    await Promise.all(pages.map((player) => player.addInitScript(() => {
      Object.defineProperty(crypto, 'randomUUID', { value: undefined })
    })))
    const sentActions = pages.map((player) => {
      const actions: string[] = []
      player.on('websocket', (socket) => socket.on('framesent', ({ payload }) => {
        const text = String(payload)
        if (text.includes('"type":"action"')) actions.push(text)
      }))
      return actions
    })
    await enter(page)
    await page.getByRole('textbox', { name: '暱稱' }).fill('玩家 1')
    await page.getByRole('button', { name: '建立房間' }).click()
    const code = page.locator('strong')
    await expect(code).toBeVisible()
    const room = await code.innerText()
    for (const [index, guest] of pages.entries()) {
      if (index === 0) continue
      await enter(guest)
      await guest.getByRole('textbox', { name: '暱稱' }).fill(`玩家 ${index + 1}`)
      await guest.getByRole('textbox', { name: '房間代碼' }).fill(room)
      await guest.getByRole('button', { name: '加入', exact: true }).click()
    }
    await page.getByRole('button', { name: '開始大老二' }).click()
    const hands = await Promise.all(pages.map(async (player) => {
      const hand = player.getByRole('group', { name: '我的手牌' })
      await expect(hand.getByRole('button')).toHaveCount(13)
      return await hand.getByRole('button').evaluateAll((buttons) => buttons.map(
        (button) => button.getAttribute('aria-label')?.slice(3) ?? '',
      ))
    }))
    expect(new Set(hands.flat()).size).toBe(52)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      await page.evaluate(() => window.innerWidth),
    )
    const table = page.locator('.live-table')
    const initialFelt = await table.evaluate((element) => getComputedStyle(element).backgroundImage)
    await page.getByRole('button', { name: '外觀設定', exact: true }).click()
    const settings = page.getByRole('dialog')
    await settings.getByRole('radio', { name: /Neon Night City/ }).check()
    await settings.getByRole('button', { name: '套用', exact: true }).click()
    await expect.poll(() => table.evaluate((element) => getComputedStyle(element).backgroundImage))
      .not.toBe(initialFelt)
    await expect(page.getByRole('group', { name: '我的手牌' }).getByRole('button')).toHaveCount(13)
    await page.screenshot({ path: info.outputPath('big-two.png'), fullPage: true })

    let actor = hands.findIndex((hand) => hand.includes('3C'))
    const opening = pages[actor]
    await opening.getByRole('button', { name: '離開房間' }).click()
    const observer = pages[(actor + 1) % 4]
    await expect(observer.getByText(`等待 玩家 ${actor + 1} 重連`)).toBeVisible()
    await enter(opening)
    await expect(opening.getByText('輪到你，首組須包含梅花 3')).toBeVisible()
    await expect(opening.getByRole('group', { name: '我的手牌' }).getByRole('button')).toHaveCount(13)

    let target: string | null = null
    let leader = actor
    let passes = 0
    for (let step = 0; step < 208 && hands.every((hand) => hand.length > 0); step += 1) {
      const player = pages[actor]
      const playable: string | undefined = step === 0 ? '3C' :
        hands[actor].find((card) => target === null || strength(card) > strength(target))
      if (playable) {
        await player.getByRole('button', { name: `選牌 ${playable}`, exact: true }).click()
        const play = player.getByRole('button', { name: '出牌', exact: true })
        if (step === 0) {
          await expect(play).toBeEnabled()
          await play.evaluate((button) => {
            const control = button as HTMLButtonElement
            control.click()
            control.click()
          })
          await expect(player.getByRole('group', { name: '我的手牌' }).getByRole('button')).toHaveCount(12)
          expect(sentActions[actor]).toHaveLength(1)
        } else {
          await play.click()
        }
        hands[actor] = hands[actor].filter((card) => card !== playable)
        target = playable
        leader = actor
        passes = 0
      } else {
        await player.getByRole('button', { name: '過牌', exact: true }).click()
        passes += 1
      }
      actor = (actor + 1) % 4
      if (passes === 3) {
        target = null
        passes = 0
        actor = leader
      }
    }
    const winner = hands.findIndex((hand) => hand.length === 0)
    expect(winner).toBeGreaterThanOrEqual(0)
    for (const player of pages) {
      await expect(player.getByText(`勝者：玩家 ${winner + 1}`)).toBeVisible()
      await expect(player.getByRole('list', { name: '本局結算' }).getByRole('listitem')).toHaveCount(4)
    }
    await page.getByRole('button', { name: '下一局' }).click()
    await expect(page.getByRole('group', { name: '我的手牌' }).getByRole('button')).toHaveCount(13)
  } finally {
    await Promise.all(contexts.map((context) => context.close()))
  }
})
