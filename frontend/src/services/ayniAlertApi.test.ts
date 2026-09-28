import { describe, expect, it, vi } from 'vitest'

import { getLatestConditions, getObservationHistory } from './ayniAlertApi'

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
  alertStates: [],
  alertDisclaimer: 'Informational project threshold only.',
  correlationId: 'request-123',
}

describe('getLatestConditions', () => {
  it('requests the encoded location and returns a valid contract', async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(latestResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    const result = await getLatestConditions('LIMA_CORPAC', undefined, request)

    expect(result).toEqual(latestResponse)
    expect(request).toHaveBeenCalledWith('/api/v1/locations/LIMA_CORPAC/latest', {
      headers: { Accept: 'application/json' },
      signal: undefined,
    })
  })

  it('preserves the stable API error code and correlation identifier', async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 'OBSERVATION_NOT_FOUND',
          message: 'no observation is available for this location',
          correlationId: 'request-404',
        }),
        { status: 404 },
      ),
    )

    await expect(getLatestConditions('LIMA_CORPAC', undefined, request)).rejects.toEqual(
      expect.objectContaining({
        status: 404,
        code: 'OBSERVATION_NOT_FOUND',
        correlationId: 'request-404',
      }),
    )
  })

  it('rejects a successful response that violates the expected contract', async () => {
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ locationId: 'LIMA_CORPAC' }), { status: 200 }),
    )

    await expect(getLatestConditions('LIMA_CORPAC', undefined, request)).rejects.toEqual(
      expect.objectContaining({
        status: 502,
        code: 'INVALID_API_RESPONSE',
      }),
    )
  })
})

describe('getObservationHistory', () => {
  it('requests a bounded history page and validates its observations', async () => {
    const { freshness: _freshness, alertStates: _alerts, alertDisclaimer: _disclaimer, ...observation } =
      latestResponse
    const historyResponse = {
      locationId: 'LIMA_CORPAC',
      items: [observation],
      page: { limit: 24, count: 1, nextCursor: null },
      correlationId: 'history-request',
    }
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(historyResponse), { status: 200 }),
    )

    const result = await getObservationHistory('LIMA_CORPAC', 24, undefined, request)

    expect(result).toEqual(historyResponse)
    expect(request).toHaveBeenCalledWith(
      '/api/v1/locations/LIMA_CORPAC/history?limit=24',
      { headers: { Accept: 'application/json' }, signal: undefined },
    )
  })
})
