<script setup lang="ts">
import { computed, ref } from 'vue'

import type { ObservationResponse } from '../types/api'

type MetricKey = keyof ObservationResponse['measurements']

const props = defineProps<{ items: ObservationResponse[] }>()
const selectedMetric = ref<MetricKey>('uvIndex')
const width = 640
const height = 200
const padding = 20

const metrics: Array<{ key: MetricKey; label: string }> = [
  { key: 'uvIndex', label: 'Índice UV' },
  { key: 'usAqi', label: 'US AQI' },
  { key: 'pm25', label: 'PM2.5' },
  { key: 'apparentTemperature', label: 'Temperatura aparente' },
]

const chronologicalItems = computed(() => [...props.items].reverse())
const selectedDefinition = computed(
  () => metrics.find((metric) => metric.key === selectedMetric.value) ?? metrics[0],
)
const selectedValues = computed(() =>
  chronologicalItems.value.map((item) => item.measurements[selectedMetric.value].value),
)
const selectedUnit = computed(
  () => chronologicalItems.value[0]?.measurements[selectedMetric.value].unit ?? '',
)
const points = computed(() => {
  const values = selectedValues.value
  if (!values.length) return ''
  const minimum = Math.min(...values)
  const maximum = Math.max(...values)
  const range = maximum - minimum || 1
  return values
    .map((value, index) => {
      const x = padding + (index * (width - padding * 2)) / Math.max(values.length - 1, 1)
      const y = height - padding - ((value - minimum) * (height - padding * 2)) / range
      return `${x},${y}`
    })
    .join(' ')
})
const rangeLabel = computed(() => {
  const values = selectedValues.value
  if (!values.length) return ''
  return `${Math.min(...values)}–${Math.max(...values)} ${selectedUnit.value}`
})

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('es-PE', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Lima',
  }).format(new Date(value))
}
</script>

<template>
  <article class="history-card">
    <div class="history-card__toolbar">
      <div>
        <p class="history-card__label">Tendencia de las últimas {{ items.length }} mediciones</p>
        <strong>{{ selectedDefinition.label }} · {{ rangeLabel }}</strong>
      </div>
      <label>
        <span>Métrica</span>
        <select v-model="selectedMetric">
          <option v-for="metric in metrics" :key="metric.key" :value="metric.key">
            {{ metric.label }}
          </option>
        </select>
      </label>
    </div>

    <svg
      class="history-chart"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      :aria-labelledby="`chart-title chart-description`"
    >
      <title id="chart-title">Tendencia de {{ selectedDefinition.label }}</title>
      <desc id="chart-description">
        Serie cronológica de {{ selectedDefinition.label }}. Rango observado: {{ rangeLabel }}.
      </desc>
      <line :x1="padding" :y1="height - padding" :x2="width - padding" :y2="height - padding" />
      <line :x1="padding" :y1="padding" :x2="padding" :y2="height - padding" />
      <polyline :points="points" />
    </svg>

    <details>
      <summary>Ver datos exactos en tabla</summary>
      <div class="table-scroll">
        <table>
          <caption>Historial ambiental reciente, de la medición más nueva a la más antigua</caption>
          <thead>
            <tr>
              <th scope="col">Hora</th>
              <th scope="col">Temperatura</th>
              <th scope="col">UV</th>
              <th scope="col">US AQI</th>
              <th scope="col">PM2.5</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.providerObservedAt">
              <th scope="row">{{ formatTime(item.providerObservedAt) }}</th>
              <td>{{ item.measurements.apparentTemperature.value }} {{ item.measurements.apparentTemperature.unit }}</td>
              <td>{{ item.measurements.uvIndex.value }}</td>
              <td>{{ item.measurements.usAqi.value }}</td>
              <td>{{ item.measurements.pm25.value }} {{ item.measurements.pm25.unit }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </article>
</template>
