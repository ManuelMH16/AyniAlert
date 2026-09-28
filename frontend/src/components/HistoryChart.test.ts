import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { ObservationResponse } from '../types/api'
import HistoryChart from './HistoryChart.vue'

const items: ObservationResponse[] = [
  observation('2026-09-28T19:00:00Z', 7.9, 50),
  observation('2026-09-28T18:00:00Z', 8.95, 52),
]

function observation(observedAt: string, uvIndex: number, usAqi: number): ObservationResponse {
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

describe('HistoryChart', () => {
  it('provides both an SVG description and an exact data table', async () => {
    const wrapper = mount(HistoryChart, { props: { items } })

    expect(wrapper.get('svg').attributes('role')).toBe('img')
    expect(wrapper.get('svg title').text()).toContain('Índice UV')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.get('table caption').text()).toContain('Historial ambiental reciente')

    await wrapper.get('select').setValue('usAqi')

    expect(wrapper.get('svg title').text()).toContain('US AQI')
    expect(wrapper.text()).toContain('50–52 USAQI')
  })
})
