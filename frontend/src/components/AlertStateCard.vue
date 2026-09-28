<script setup lang="ts">
import { computed } from 'vue'

import type { AlertState } from '../types/api'

const props = defineProps<{ state: AlertState }>()

const labels: Record<AlertState['alertType'], string> = {
  APPARENT_TEMPERATURE: 'Temperatura aparente',
  UV_INDEX: 'Radiación UV',
  US_AQI: 'Calidad del aire',
}

const title = computed(() => labels[props.state.alertType])
const stateLabel = computed(() => {
  if (props.state.status === 'INACTIVE') return 'Sin alerta activa'
  if (props.state.severity === 'ADVISORY') return 'Aviso informativo'
  if (props.state.severity === 'HIGH') return 'Nivel alto'
  return 'Nivel crítico'
})
</script>

<template>
  <article
    class="alert-card"
    :class="[`alert-card--${state.status.toLowerCase()}`, `alert-card--${state.severity?.toLowerCase() ?? 'none'}`]"
  >
    <div>
      <p class="alert-card__title">{{ title }}</p>
      <p class="alert-card__time">Evaluado a las {{ new Date(state.observedAt).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' }) }}</p>
    </div>
    <strong class="alert-card__badge">{{ stateLabel }}</strong>
  </article>
</template>
