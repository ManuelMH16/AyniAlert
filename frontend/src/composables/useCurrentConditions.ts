import { onBeforeUnmount, onMounted, ref } from 'vue'

import {
  AyniAlertApiError,
  getLatestConditions,
} from '../services/ayniAlertApi'
import type { LatestConditionsResponse } from '../types/api'

export type CurrentConditionsViewState = 'loading' | 'ready' | 'empty' | 'unavailable'

export function useCurrentConditions() {
  const data = ref<LatestConditionsResponse | null>(null)
  const viewState = ref<CurrentConditionsViewState>('loading')
  const errorMessage = ref('')
  let controller: AbortController | null = null

  async function load(): Promise<void> {
    controller?.abort()
    const activeController = new AbortController()
    controller = activeController
    viewState.value = 'loading'
    errorMessage.value = ''

    try {
      data.value = await getLatestConditions('LIMA_CORPAC', activeController.signal)
      viewState.value = 'ready'
    } catch (error) {
      if (activeController.signal.aborted) return
      data.value = null
      if (error instanceof AyniAlertApiError && error.code === 'OBSERVATION_NOT_FOUND') {
        viewState.value = 'empty'
        return
      }
      errorMessage.value =
        error instanceof AyniAlertApiError
          ? error.message
          : 'No pudimos consultar las condiciones ambientales.'
      viewState.value = 'unavailable'
    }
  }

  onMounted(load)
  onBeforeUnmount(() => controller?.abort())

  return { data, viewState, errorMessage, reload: load }
}
