export type FreshnessStatus = 'FRESH' | 'STALE'
export type AlertStatus = 'INACTIVE' | 'ACTIVE'
export type AlertSeverity = 'ADVISORY' | 'HIGH' | 'CRITICAL' | null
export type AlertType = 'APPARENT_TEMPERATURE' | 'UV_INDEX' | 'US_AQI'

export interface MeasurementValue {
  value: number
  unit: string
}

export interface AlertState {
  alertType: AlertType
  ruleVersion: number
  measurement: AlertType
  status: AlertStatus
  severity: AlertSeverity
  value: number
  observationId: string
  observedAt: string
}

export interface ObservationResponse {
  schemaVersion: number
  locationId: string
  providerObservedAt: string
  ingestedAt: string
  coordinates: {
    latitude: number
    longitude: number
  }
  measurements: {
    apparentTemperature: MeasurementValue
    uvIndex: MeasurementValue
    usAqi: MeasurementValue
    pm25: MeasurementValue
  }
  source: {
    provider: string
    weatherObservedAt: string
    airQualityObservedAt: string
  }
}

export interface LatestConditionsResponse extends ObservationResponse {
  freshness: {
    status: FreshnessStatus
    ageSeconds: number
  }
  alertStates: AlertState[]
  alertDisclaimer: string
  correlationId: string
}

export interface ObservationHistoryResponse {
  locationId: string
  items: ObservationResponse[]
  page: {
    limit: number
    count: number
    nextCursor: string | null
  }
  correlationId: string
}

export interface ApiErrorResponse {
  code: string
  message: string
  correlationId: string
}
