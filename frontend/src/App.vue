<script setup lang="ts">
import AlertStateCard from './components/AlertStateCard.vue'
import ConditionCard from './components/ConditionCard.vue'
import FreshnessBanner from './components/FreshnessBanner.vue'
import HistoryChart from './components/HistoryChart.vue'
import { useCurrentConditions } from './composables/useCurrentConditions'
import { useObservationHistory } from './composables/useObservationHistory'

const { data, viewState, errorMessage, reload } = useCurrentConditions()
const {
  items: historyItems,
  viewState: historyViewState,
  errorMessage: historyErrorMessage,
  reload: reloadHistory,
} = useObservationHistory()
</script>

<template>
  <header class="site-header">
    <a class="brand" href="/" aria-label="AyniAlert, inicio">
      <span class="brand__mark" aria-hidden="true">A</span>
      <span>AyniAlert</span>
    </a>
    <span class="location">Corpac · Lima</span>
  </header>

  <main class="page-shell">
    <section class="intro" aria-labelledby="page-title">
      <p class="eyebrow">Información ambiental comunitaria</p>
      <h1 id="page-title">Entendé las condiciones ambientales de tu zona</h1>
      <p class="intro__copy">
        Mediciones recientes y alertas informativas para tomar decisiones cotidianas con mejor contexto.
      </p>
    </section>

    <section v-if="viewState === 'loading'" class="state-panel" aria-live="polite" aria-busy="true">
      <span class="loader" aria-hidden="true"></span>
      <h2>Consultando condiciones</h2>
      <p>Estamos obteniendo la medición más reciente.</p>
    </section>

    <section v-else-if="viewState === 'empty'" class="state-panel" role="status">
      <h2>Todavía no hay mediciones</h2>
      <p>Volvé a consultar en unos minutos.</p>
      <button type="button" @click="reload">Actualizar</button>
    </section>

    <section v-else-if="viewState === 'unavailable'" class="state-panel state-panel--error" role="alert">
      <h2>Información temporalmente no disponible</h2>
      <p>{{ errorMessage }}</p>
      <button type="button" @click="reload">Reintentar</button>
    </section>

    <template v-else-if="data">
      <FreshnessBanner :status="data.freshness.status" :observed-at="data.providerObservedAt" />

      <section aria-labelledby="conditions-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Última observación</p>
            <h2 id="conditions-title">Condiciones actuales</h2>
          </div>
          <span>{{ data.source.provider }}</span>
        </div>

        <div class="conditions-grid">
          <ConditionCard
            label="Temperatura aparente"
            :value="data.measurements.apparentTemperature.value"
            :unit="data.measurements.apparentTemperature.unit"
            description="Cómo se percibe la temperatura exterior."
          />
          <ConditionCard
            label="Índice UV"
            :value="data.measurements.uvIndex.value"
            :unit="data.measurements.uvIndex.unit"
            description="Intensidad estimada de radiación ultravioleta."
          />
          <ConditionCard
            label="Calidad del aire"
            :value="data.measurements.usAqi.value"
            :unit="data.measurements.usAqi.unit"
            description="Índice de calidad del aire según escala US AQI."
          />
          <ConditionCard
            label="Partículas PM2.5"
            :value="data.measurements.pm25.value"
            :unit="data.measurements.pm25.unit"
            description="Concentración de partículas finas en el aire."
          />
        </div>
      </section>

      <section class="history-section" aria-labelledby="history-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Evolución reciente</p>
            <h2 id="history-title">Historial ambiental</h2>
          </div>
        </div>
        <div v-if="historyViewState === 'loading'" class="inline-state" aria-live="polite">
          Cargando historial…
        </div>
        <HistoryChart v-else-if="historyViewState === 'ready'" :items="historyItems" />
        <div v-else-if="historyViewState === 'empty'" class="inline-state">
          Todavía no hay suficientes observaciones para mostrar una tendencia.
        </div>
        <div v-else class="inline-state inline-state--error" role="alert">
          <span>{{ historyErrorMessage }}</span>
          <button type="button" @click="reloadHistory">Reintentar historial</button>
        </div>
      </section>

      <section class="alerts-section" aria-labelledby="alerts-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Interpretación del proyecto</p>
            <h2 id="alerts-title">Estado de alertas</h2>
          </div>
        </div>
        <div v-if="data.alertStates.length" class="alerts-list">
          <AlertStateCard v-for="state in data.alertStates" :key="state.alertType" :state="state" />
        </div>
        <p v-else class="empty-inline">Los estados de alerta todavía están siendo evaluados.</p>
      </section>

      <aside class="disclaimer" aria-labelledby="disclaimer-title">
        <h2 id="disclaimer-title">Uso responsable</h2>
        <p>{{ data.alertDisclaimer }}</p>
        <p>
          Datos ambientales provistos por
          <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>.
          AyniAlert no es un sistema oficial de emergencias.
        </p>
      </aside>
    </template>
  </main>
</template>
