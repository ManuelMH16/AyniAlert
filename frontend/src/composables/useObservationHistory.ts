import { onBeforeUnmount, onMounted, ref } from 'vue'

import { AyniAlertApiError, getObservationHistory } from '../services/ayniAlertApi'
import type { ObservationResponse } from '../types/api'

export type HistoryViewState = 'loading' | 'ready' | 'empty' | 'unavailable'

export function useObservationHistory() {
  const items = ref<ObservationResponse[]>([])
  const viewState = ref<HistoryViewState>('loading')
  const errorMessage = ref('')
  let controller: AbortController | null = null

  async function load(): Promise<void> {
    controller?.abort()
    const activeController = new AbortController()
    controller = activeController
    viewState.value = 'loading'
    errorMessage.value = ''

    try {
      const response = await getObservationHistory('LIMA_CORPAC', 24, activeController.signal)
      items.value = response.items
      viewState.value = response.items.length ? 'ready' : 'empty'
    } catch (error) {
      if (activeController.signal.aborted) return
      items.value = []
      errorMessage.value =
        error instanceof AyniAlertApiError
          ? error.message
          : 'No pudimos consultar el historial reciente.'
      viewState.value = 'unavailable'
    }
  }

  onMounted(load)
  onBeforeUnmount(() => controller?.abort())

  return { items, viewState, errorMessage, reload: load }
}
