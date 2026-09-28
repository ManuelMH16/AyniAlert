import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConditionCard from './ConditionCard.vue'

describe('ConditionCard', () => {
  it('renders the measurement label, value, unit, and explanation', () => {
    const wrapper = mount(ConditionCard, {
      props: {
        label: 'Índice UV',
        value: 7.9,
        unit: 'index',
        description: 'Intensidad estimada de radiación ultravioleta.',
      },
    })

    expect(wrapper.text()).toContain('Índice UV')
    expect(wrapper.text()).toContain('7.9')
    expect(wrapper.text()).toContain('index')
    expect(wrapper.text()).toContain('Intensidad estimada')
  })
})
