import { test, expect } from '@playwright/test'

test('繁中首頁透過真實 API 檢查連線，無水平溢出', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/好牌，好朋友。\s*相聚同一桌。/)
  await expect(page.getByRole('heading', { name: '遊戲大廳' })).toBeVisible()
  await page.getByRole('button', { name: '檢查 API 連線' }).click()
  await expect(page.getByRole('status')).toContainText('API 連線正常')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: test.info().outputPath('foundation.png'), fullPage: true })
})

test('網路失敗提供可重試的錯誤', async ({ page }) => {
  await page.goto('/')
  await page.route('**/api/health/live', route => route.abort('failed'))
  await page.getByRole('button', { name: '檢查 API 連線' }).click()
  await expect(page.getByRole('status')).toContainText('無法連線至 API')
  await page.unroute('**/api/health/live')
  await page.getByRole('button', { name: '檢查 API 連線' }).click()
  await expect(page.getByRole('status')).toContainText('API 連線正常')
})
