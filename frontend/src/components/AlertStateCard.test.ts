import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AlertStateCard from './AlertStateCard.vue'

describe('AlertStateCard', () => {
  it('explains an active advisory without presenting it as an official warning', () => {
    const wrapper = mount(AlertStateCard, {
      props: {
        state: {
          alertType: 'UV_INDEX',
          ruleVersion: 1,
          measurement: 'UV_INDEX',
          status: 'ACTIVE',
          severity: 'ADVISORY',
          value: 7.9,
          observationId: 'LIMA_CORPAC#2026-09-28T19:00:00Z',
          observedAt: '2026-09-28T19:00:00Z',
        },
      },
    })

    expect(wrapper.text()).toContain('Radiación UV')
    expect(wrapper.text()).toContain('Aviso informativo')
    expect(wrapper.text()).not.toContain('Emergencia')
  })

  it('labels an inactive state explicitly', () => {
    const wrapper = mount(AlertStateCard, {
      props: {
        state: {
          alertType: 'US_AQI',
          ruleVersion: 1,
          measurement: 'US_AQI',
          status: 'INACTIVE',
          severity: null,
          value: 50,
          observationId: 'LIMA_CORPAC#2026-09-28T19:00:00Z',
          observedAt: '2026-09-28T19:00:00Z',
        },
      },
    })

    expect(wrapper.text()).toContain('Sin alerta activa')
  })
})
