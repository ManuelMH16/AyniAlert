# AyniAlert Requirements

## 1. Purpose

AyniAlert provides clear, timestamped environmental conditions and configurable alerts for a single pilot location in Corpac, Lima. The MVP is an informational and educational system, not a medical device or an official emergency-warning service.

## 2. Glossary

- **Observation:** Normalized weather and air-quality measurements for one location and provider timestamp.
- **Alert rule:** Versioned configuration that maps a measurement to a severity.
- **Alert transition:** A change between `INACTIVE`, `ACTIVE`, or a different severity.
- **Fresh data:** An observation whose provider timestamp is no more than two hours old.
- **Pilot location:** `LIMA_CORPAC`, represented by public neighborhood-level coordinates rather than a private address.
- **Provider:** Open-Meteo Weather API and Open-Meteo Air Quality API.

## 3. Functional Requirements

### REQ-1 — Scheduled environmental data ingestion

**User story:** As a community user, I want recent environmental measurements so that I can understand current outdoor conditions.

#### Acceptance criteria

1. WHEN the hourly schedule runs, THE SYSTEM SHALL request weather and air-quality data for `LIMA_CORPAC`.
2. THE SYSTEM SHALL retrieve, at minimum, apparent temperature, UV index, US AQI, and PM2.5 when those values are supplied by the provider.
3. WHEN provider responses are valid, THE SYSTEM SHALL normalize them into one observation with location, provider timestamps, ingestion timestamp, units, source, and schema version.
4. THE SYSTEM SHALL store an observation idempotently using the location and provider observation time.
5. IF the provider response is incomplete or invalid, THEN THE SYSTEM SHALL reject the observation, emit a structured error, and preserve the last valid observation.
6. IF one provider endpoint fails, THEN THE SYSTEM SHALL NOT represent partially combined data as a complete observation.

### REQ-2 — Current conditions API

**User story:** As a community user, I want to retrieve the latest conditions through a simple API.

#### Acceptance criteria

1. WHEN `GET /v1/locations/LIMA_CORPAC/latest` is called, THE SYSTEM SHALL return the latest valid observation and current alert states.
2. THE response SHALL include the provider timestamp, ingestion timestamp, units, source attribution, and a freshness status.
3. IF no observation exists, THEN THE SYSTEM SHALL return HTTP `404` with a stable machine-readable error code.
4. THE public API SHALL expose read-only operations only.
5. WHEN an unsupported location identifier is supplied, THE SYSTEM SHALL return HTTP `404` without querying DynamoDB using unvalidated input.

### REQ-3 — Recent observation history

**User story:** As a community user, I want recent history so that I can see how conditions have changed.

#### Acceptance criteria

1. WHEN `GET /v1/locations/LIMA_CORPAC/history` is called, THE SYSTEM SHALL return observations in descending provider-time order.
2. THE endpoint SHALL accept bounded `from`, `to`, and `limit` parameters.
3. THE `limit` SHALL default to 24 and SHALL NOT exceed 168 observations.
4. IF query parameters are invalid, THEN THE SYSTEM SHALL return HTTP `400` with a stable machine-readable error code.
5. THE SYSTEM SHALL NOT perform an unbounded table scan.

### REQ-4 — Configurable alert evaluation

**User story:** As a community user, I want notable conditions highlighted consistently.

#### Acceptance criteria

1. WHEN an `ObservationRecorded` event is received, THE SYSTEM SHALL evaluate enabled, versioned alert rules.
2. THE MVP SHALL support rules for apparent temperature, UV index, and US AQI without hard-coding thresholds in Lambda handlers.
3. THE SYSTEM SHALL record the current state and history of alert transitions.
4. WHEN repeated observations produce the same alert state and severity, THE SYSTEM SHALL NOT create a duplicate transition.
5. THE dashboard and API SHALL label alerts as informational project thresholds and SHALL NOT express medical diagnoses or guarantees of safety.
6. Rule documentation SHALL identify the source or rationale for every configured threshold before production deployment.

### REQ-5 — Opt-in alert notification

**User story:** As a subscriber, I want notifications only when relevant alert states change.

#### Acceptance criteria

1. WHEN an alert opens, changes severity, or closes, THE SYSTEM SHALL publish one notification event.
2. THE SYSTEM SHALL NOT publish a notification for an unchanged state.
3. Amazon SNS SHALL manage subscription confirmation and delivery.
4. THE application SHALL NOT store subscriber email addresses or phone numbers in DynamoDB.
5. Every message SHALL include location, alert type, severity, observation time, and the informational-use disclaimer.

### REQ-6 — Public dashboard

**User story:** As a community user, I want a mobile-friendly dashboard that explains current conditions without requiring an account.

#### Acceptance criteria

1. THE dashboard SHALL display apparent temperature, UV index, US AQI, PM2.5, alert states, data source, and last update time.
2. THE dashboard SHALL distinguish fresh, stale, unavailable, and loading states.
3. THE dashboard SHALL display the project disclaimer and link to provider attribution.
4. THE dashboard SHALL remain usable at viewport widths of 360 pixels and above.
5. THE dashboard SHALL NOT claim that the service is an official warning system.

### REQ-7 — Health and operational visibility

**User story:** As the operator, I want failures to be visible so that stale or missing data is not silently presented as current.

#### Acceptance criteria

1. WHEN `GET /health` is called, THE SYSTEM SHALL return application availability without exposing credentials or internal stack traces.
2. Lambda functions SHALL emit structured JSON logs containing service, operation, outcome, and correlation identifier.
3. THE SYSTEM SHALL publish metrics for ingestion success, ingestion failure, rejected provider responses, stale data, alert transitions, and API errors.
4. THE SYSTEM SHALL alarm after repeated ingestion failures or when no fresh observation has been stored for more than two hours.
5. Log groups SHALL have an explicit retention period.

## 4. Quality Attribute Requirements

### REQ-8 — Security

1. Every Lambda function SHALL have a distinct least-privilege IAM role.
2. THE public API SHALL permit only documented read routes and SHALL apply throttling.
3. THE dashboard S3 bucket SHALL block public access and SHALL be accessible through CloudFront Origin Access Control.
4. THE SYSTEM SHALL use HTTPS for public traffic.
5. AWS credentials and environment-specific secrets SHALL NOT be committed to Git.

### REQ-9 — Reliability

1. Scheduled ingestion SHALL be idempotent.
2. External calls SHALL use explicit connection and read timeouts.
3. Event delivery SHALL use bounded retries and dead-letter handling.
4. IF current data is unavailable, THEN THE SYSTEM SHALL expose the last valid observation with a stale indicator rather than silently changing its timestamp.
5. A failed deployment SHALL be recoverable by redeploying a previously versioned infrastructure template and artifact.

### REQ-10 — Performance

1. At the expected MVP load, the read API SHALL target a p95 server response time below two seconds.
2. History responses SHALL be bounded and paginated when more data is available.
3. The implementation SHALL use key-based DynamoDB queries and SHALL NOT scan the table for public requests.

### REQ-11 — Cost efficiency

1. The MVP SHALL use on-demand or request-based managed services where practical.
2. Detailed observations SHALL have a configurable retention period, initially 30 days.
3. An AWS Budget SHALL be configured before recurring workloads are deployed.
4. A documented monthly cost estimate SHALL exist before the first public release.
5. Generative AI SHALL remain outside the MVP unless a measurable user need justifies its cost and complexity.

### REQ-12 — Testability and delivery

1. Domain normalization and alert evaluation SHALL be testable without AWS credentials or network access.
2. Provider clients and persistence adapters SHALL be replaceable with test doubles.
3. Infrastructure SHALL be reproducible from version-controlled AWS SAM templates.
4. Automated checks SHALL cover unit tests, template validation, and frontend tests before deployment.
5. Deployment evidence SHALL identify the commit and environment being demonstrated.

## 5. MVP Success Criteria

The MVP is complete only when:

1. Infrastructure deploys reproducibly from the repository.
2. A scheduled invocation stores a real, valid observation.
3. The API returns the latest observation and freshness state.
4. The dashboard displays real data from the deployed API.
5. At least one configured rule opens and closes without duplicate notifications.
6. Automated checks pass and operational alarms exist.
7. The repository contains cost, security, and deployment evidence.
