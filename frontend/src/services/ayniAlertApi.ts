import type {
  ApiErrorResponse,
  LatestConditionsResponse,
  ObservationHistoryResponse,
  ObservationResponse,
} from '../types/api'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, '')

export class AyniAlertApiError extends Error {
  readonly status: number
  readonly code: string
  readonly correlationId?: string

  constructor(
    status: number,
    code: string,
    message: string,
    correlationId?: string,
  ) {
    super(message)
    this.name = 'AyniAlertApiError'
    this.status = status
    this.code = code
    this.correlationId = correlationId
  }
}

export async function getLatestConditions(
  locationId = 'LIMA_CORPAC',
  signal?: AbortSignal,
  request: typeof fetch = fetch,
): Promise<LatestConditionsResponse> {
  const response = await request(
    `${apiBaseUrl}/v1/locations/${encodeURIComponent(locationId)}/latest`,
    {
      headers: { Accept: 'application/json' },
      signal,
    },
  )

  if (!response.ok) {
    const error = await readApiError(response)
    throw new AyniAlertApiError(response.status, error.code, error.message, error.correlationId)
  }

  const body: unknown = await response.json()
  if (!isLatestConditionsResponse(body)) {
    throw new AyniAlertApiError(502, 'INVALID_API_RESPONSE', 'La API devolvió datos no válidos.')
  }
  return body
}

export async function getObservationHistory(
  locationId = 'LIMA_CORPAC',
  limit = 24,
  signal?: AbortSignal,
  request: typeof fetch = fetch,
): Promise<ObservationHistoryResponse> {
  const parameters = new URLSearchParams({ limit: String(limit) })
  const response = await request(
    `${apiBaseUrl}/v1/locations/${encodeURIComponent(locationId)}/history?${parameters}`,
    {
      headers: { Accept: 'application/json' },
      signal,
    },
  )
  if (!response.ok) {
    const error = await readApiError(response)
    throw new AyniAlertApiError(response.status, error.code, error.message, error.correlationId)
  }
  const body: unknown = await response.json()
  if (!isObservationHistoryResponse(body)) {
    throw new AyniAlertApiError(502, 'INVALID_API_RESPONSE', 'La API devolvió datos no válidos.')
  }
  return body
}

async function readApiError(response: Response): Promise<ApiErrorResponse> {
  try {
    const body: unknown = await response.json()
    if (isApiErrorResponse(body)) return body
  } catch {
    // A stable fallback keeps transport details out of the interface.
  }
  return {
    code: 'API_UNAVAILABLE',
    message: 'No pudimos consultar las condiciones ambientales.',
    correlationId: '',
  }
}

function isLatestConditionsResponse(value: unknown): value is LatestConditionsResponse {
  if (!isObservation(value)) {
    return false
  }
  const candidate = value as ObservationResponse & {
    freshness?: unknown
    alertDisclaimer?: unknown
    alertStates?: unknown
  }
  if (!isRecord(candidate.freshness)) return false
  return (
    typeof candidate.alertDisclaimer === 'string' &&
    Array.isArray(candidate.alertStates) &&
    (candidate.freshness.status === 'FRESH' || candidate.freshness.status === 'STALE')
  )
}

function isObservationHistoryResponse(value: unknown): value is ObservationHistoryResponse {
  return (
    isRecord(value) &&
    typeof value.locationId === 'string' &&
    Array.isArray(value.items) &&
    value.items.every(isObservation) &&
    isRecord(value.page) &&
    typeof value.page.limit === 'number' &&
    typeof value.page.count === 'number' &&
    (typeof value.page.nextCursor === 'string' || value.page.nextCursor === null) &&
    typeof value.correlationId === 'string'
  )
}

function isObservation(value: unknown): value is ObservationResponse {
  if (!isRecord(value) || !isRecord(value.measurements) || !isRecord(value.source)) return false
  return (
    typeof value.locationId === 'string' &&
    typeof value.providerObservedAt === 'string' &&
    typeof value.ingestedAt === 'string' &&
    isMeasurement(value.measurements.apparentTemperature) &&
    isMeasurement(value.measurements.uvIndex) &&
    isMeasurement(value.measurements.usAqi) &&
    isMeasurement(value.measurements.pm25)
  )
}

function isMeasurement(value: unknown): boolean {
  return isRecord(value) && typeof value.value === 'number' && typeof value.unit === 'string'
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  return (
    isRecord(value) &&
    typeof value.code === 'string' &&
    typeof value.message === 'string' &&
    typeof value.correlationId === 'string'
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
