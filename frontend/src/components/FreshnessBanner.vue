<script setup lang="ts">
import type { FreshnessStatus } from '../types/api'

defineProps<{
  status: FreshnessStatus
  observedAt: string
}>()

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat('es-PE', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Lima',
  }).format(new Date(value))
}
</script>

<template>
  <div class="freshness" :class="`freshness--${status.toLowerCase()}`" role="status">
    <span class="freshness__dot" aria-hidden="true"></span>
    <p>
      <strong>{{ status === 'FRESH' ? 'Datos recientes' : 'Datos desactualizados' }}</strong>
      <span>Última medición: {{ formatTimestamp(observedAt) }}</span>
    </p>
  </div>
</template>
