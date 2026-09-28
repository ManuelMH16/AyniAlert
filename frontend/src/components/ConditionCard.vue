<script setup lang="ts">
defineProps<{
  label: string
  value: number
  unit: string
  description: string
}>()
</script>

<template>
  <article class="condition-card">
    <p class="condition-card__label">{{ label }}</p>
    <p class="condition-card__reading">
      <strong>{{ value }}</strong>
      <span>{{ unit }}</span>
    </p>
    <p class="condition-card__description">{{ description }}</p>
  </article>
</template>
