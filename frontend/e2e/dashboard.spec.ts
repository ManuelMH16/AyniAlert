import { expect, test, type Page } from '@playwright/test'

const latestResponse = {
  schemaVersion: 1,
  locationId: 'LIMA_CORPAC',
  providerObservedAt: '2026-09-28T19:00:00Z',
  ingestedAt: '2026-09-28T19:03:00Z',
  coordinates: { latitude: -12.0982, longitude: -77.0143 },
  measurements: {
    apparentTemperature: { value: 26.4, unit: '°C' },
    uvIndex: { value: 7.9, unit: 'index' },
    usAqi: { value: 50, unit: 'USAQI' },
    pm25: { value: 9.4, unit: 'μg/m³' },
  },
  source: {
    provider: 'Open-Meteo',
    weatherObservedAt: '2026-09-28T19:00:00Z',
    airQualityObservedAt: '2026-09-28T19:00:00Z',
  },
  freshness: { status: 'FRESH', ageSeconds: 120 },
  alertStates: [
    {
      alertType: 'US_AQI',
      ruleVersion: 1,
      measurement: 'US_AQI',
      status: 'INACTIVE',
      severity: null,
      value: 50,
      observationId: 'LIMA_CORPAC#2026-09-28T19:00:00Z',
      observedAt: '2026-09-28T19:00:00Z',
    },
    {
      alertType: 'UV_INDEX',
      ruleVersion: 1,
      measurement: 'UV_INDEX',
      status: 'ACTIVE',
      severity: 'ADVISORY',
      value: 7.9,
      observationId: 'LIMA_CORPAC#2026-09-28T19:00:00Z',
      observedAt: '2026-09-28T19:00:00Z',
    },
  ],
  alertDisclaimer: 'Informational project threshold only; not medical advice.',
  correlationId: 'latest-request',
}

const historyResponse = {
  locationId: 'LIMA_CORPAC',
  items: [
    observation('2026-09-28T19:00:00Z', 7.9, 50),
    observation('2026-09-28T18:00:00Z', 8.95, 52),
  ],
  page: { limit: 24, count: 2, nextCursor: null },
  correlationId: 'history-request',
}

test.beforeEach(async ({ page }) => {
  await mockSuccessfulApi(page)
})

test('shows current conditions, alerts, and accessible history', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Condiciones actuales' })).toBeVisible()
  await expect(page.getByText('26.4', { exact: true })).toBeVisible()
  await expect(page.getByText('Datos recientes')).toBeVisible()
  await expect(page.getByText('Aviso informativo')).toBeVisible()
  await expect(page.getByText('Sin alerta activa')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historial ambiental' })).toBeVisible()
  await expect(page.getByRole('img', { name: /Tendencia de Índice UV/ })).toBeVisible()

  await page.getByText('Ver datos exactos en tabla').click()
  await expect(page.getByRole('table')).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(2)
})

test('changes the historical metric and has no horizontal page overflow', async ({ page }) => {
  await page.goto('/')
  const metric = page.getByLabel('Métrica')
  await expect(metric).toBeVisible()
  await metric.selectOption('usAqi')
  await expect(page.getByRole('img', { name: /Tendencia de US AQI/ })).toBeVisible()

  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    content: document.documentElement.scrollWidth,
  }))
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
})

test('presents an actionable unavailable state without leaking API details', async ({ page }) => {
  await page.unroute('**/api/v1/locations/LIMA_CORPAC/latest')
  await page.route('**/api/v1/locations/LIMA_CORPAC/latest', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 'API_UNAVAILABLE',
        message: 'No pudimos consultar las condiciones ambientales.',
        correlationId: 'failure-request',
      }),
    })
  })

  await page.goto('/')

  const alert = page.getByRole('alert')
  await expect(alert).toContainText('Información temporalmente no disponible')
  await expect(alert.getByRole('button', { name: 'Reintentar' })).toBeVisible()
  await expect(alert).not.toContainText('failure-request')
})

async function mockSuccessfulApi(page: Page): Promise<void> {
  await page.route('**/api/v1/locations/LIMA_CORPAC/latest', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(latestResponse),
    })
  })
  await page.route('**/api/v1/locations/LIMA_CORPAC/history?*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(historyResponse),
    })
  })
}

function observation(observedAt: string, uvIndex: number, usAqi: number) {
  return {
    schemaVersion: 1,
    locationId: 'LIMA_CORPAC',
    providerObservedAt: observedAt,
    ingestedAt: observedAt,
    coordinates: { latitude: -12.0982, longitude: -77.0143 },
    measurements: {
      apparentTemperature: { value: 26.4, unit: '°C' },
      uvIndex: { value: uvIndex, unit: 'index' },
      usAqi: { value: usAqi, unit: 'USAQI' },
      pm25: { value: 9.4, unit: 'μg/m³' },
    },
    source: {
      provider: 'Open-Meteo',
      weatherObservedAt: observedAt,
      airQualityObservedAt: observedAt,
    },
  }
}
