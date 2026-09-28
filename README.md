# AyniAlert

> A serverless community environmental alert platform for Lima, Peru.

[![Project status: In development](https://img.shields.io/badge/status-in%20development-blue)](#project-status)
[![AWS](https://img.shields.io/badge/cloud-AWS-232F3E?logo=amazonwebservices)](#proposed-aws-architecture)
[![Infrastructure as Code](https://img.shields.io/badge/IaC-AWS%20SAM-blue)](#technology-stack)

## Overview

AyniAlert is an in-development platform designed to make local environmental conditions easier to understand. It will periodically collect public weather and air-quality data for Lima, evaluate configurable risk thresholds, and expose the results through a public dashboard and opt-in notifications.

The first version focuses on three conditions:

- High apparent temperature
- High ultraviolet radiation
- Poor air quality

The project is intentionally starting with a small, deployable vertical slice. The goal is to demonstrate how a low-cost, event-driven AWS architecture can transform public data into accessible community information without claiming medical authority or replacing official emergency services.

## Problem

Environmental data is available from multiple sources, but raw measurements are not always easy to interpret quickly. People who exercise outdoors, work outside, care for older adults, or have environmental sensitivities may benefit from a simple view of current conditions and configurable warnings.

### Target users

- Residents checking conditions before outdoor activities
- Outdoor workers and commuters
- Caregivers supporting older adults or other vulnerable people
- Community organizations sharing local environmental information

## MVP Scope

The minimum viable product will:

1. Retrieve environmental data for one configured Lima location on a schedule.
2. Store normalized observations with timestamps and source metadata.
3. Evaluate configurable alert rules.
4. Expose current conditions and recent history through a read-only API.
5. Display the information in a public responsive dashboard.
6. Send opt-in notifications when an alert changes state.
7. Record operational metrics and failures in Amazon CloudWatch.

### Out of scope for the MVP

- Medical recommendations or diagnoses
- Emergency-response coordination
- User-submitted environmental measurements
- Machine-learning predictions
- Generative-AI summaries
- Native mobile applications
- Multi-region disaster recovery

These exclusions keep the first release small enough to deploy, observe, and improve using evidence rather than assumptions.

## Project Status

| Capability | Status |
|---|---|
| Problem statement and MVP scope | Documented |
| Proposed AWS architecture | Documented |
| Infrastructure as Code | Implemented; SAM validation passing |
| Environmental ingestion | Lambda and hourly schedule deployed; manual and automatic ingestion verified in AWS |
| Alert evaluation | Evaluator Lambda deployed; conditional state and transition persistence verified in `dev` |
| Observation events | Custom EventBridge routing, bounded retries, and SQS dead-letter handling verified in `dev` |
| Health API | Deployed and publicly verified in the `dev` stage |
| Latest-observation API | Latest conditions and current location-scoped alert states deployed and publicly verified in `dev` |
| Observation-history API | Deployed and publicly verified with pagination and validation |
| Public API contract | OpenAPI 3.1 checked in; four deployed smoke tests passing against `dev` |
| Public dashboard | Vue 3 TypeScript conditions, alert states, and accessible history experience implemented locally; deployment pending |
| Opt-in notifications | SNS topic, confirmed opt-in subscription, and transition-only delivery verified in `dev` |
| Automated tests | 91 backend and 8 frontend tests passing; four opt-in deployed smoke tests passing |
| Deployment pipeline | Planned |

No production deployment is claimed at this stage. In the `dev` environment in `us-east-1`, manual and hourly scheduled Lambda invocations successfully persisted real Open-Meteo observations for `LIMA_CORPAC`. End-to-end ingestion verified automatic `ObservationRecorded` delivery through the custom EventBridge bus, atomic alert-state persistence, and an empty delivery DLQ. A real UV change from `HIGH` to `ADVISORY` produced one `SEVERITY_CHANGED` message through SNS to a confirmed opt-in subscription; replaying the same observation produced no second transition or notification. The public latest endpoint was then verified returning that same UV state as `ACTIVE/ADVISORY` and US AQI as `INACTIVE`, with state-specific observation timestamps and an informational disclaimer. The health and observation-history routes have also been verified through API Gateway. Local verification includes 91 backend tests, while four opt-in smoke tests pass against the deployed `dev` API. Coverage includes provider-response normalization, idempotent DynamoDB serialization, bounded history pagination, current-alert-state projection, the checked-in OpenAPI contract, pure alert evaluation and transitions, EventBridge and SNS publication, conditional alert-state persistence, Python linting, and AWS SAM template validation.

### Verified development endpoints

```text
GET https://sjf63cndec.execute-api.us-east-1.amazonaws.com/dev/health
GET https://sjf63cndec.execute-api.us-east-1.amazonaws.com/dev/v1/locations/LIMA_CORPAC/latest
GET https://sjf63cndec.execute-api.us-east-1.amazonaws.com/dev/v1/locations/LIMA_CORPAC/history?limit=24
```

These endpoints belong to a development environment and may change or be removed without notice.

## Local Development

### Prerequisites

- Python 3.13 or 3.14
- Node.js 24 LTS for dashboard development
- AWS CLI v2
- AWS SAM CLI
- Docker for SAM local emulation

### Set up the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "pytest>=8.3,<9" "ruff>=0.11,<1"
```

### Run automated checks

```bash
python -m pytest
python -m ruff check .
sam validate --lint --template-file template.yaml
```

Expected current result:

```text
91 passed, 4 skipped
All checks passed!
template.yaml is a valid SAM Template
```

The skipped tests are network-dependent deployment checks. Run them explicitly against a public stage:

```bash
AYNI_ALERT_API_BASE_URL="https://sjf63cndec.execute-api.us-east-1.amazonaws.com/dev" \
  python -m pytest backend/tests/smoke
```

Expected deployed result:

```text
4 passed
```

The versioned OpenAPI 3.1 contract is stored at `docs/api/openapi.json`.

### Run the dashboard locally

```bash
cd frontend
npm install
npm run typecheck
npm run test:run
npm run dev
```

The development server proxies `/api` to the verified `dev` API, so local development does not require permissive CORS. Current frontend verification is `8 passed`; proxy checks returned both deployed alert states and 21 recent observations. The history chart supports all four measurements and includes an exact tabular alternative.

### AWS authentication

Use an individual IAM or IAM Identity Center identity with MFA and least privilege. Do not use the root user for development and do not commit access keys. Deployment instructions will be added after the development account, region, budget, and permissions are configured.

## Proposed AWS Architecture

```mermaid
flowchart LR
    Source[Open-Meteo APIs]
    Scheduler[Amazon EventBridge Scheduler]
    Ingest[AWS Lambda<br/>Data ingestion]
    DB[(Amazon DynamoDB)]
    Bus[Amazon EventBridge<br/>Custom event bus]
    Evaluate[AWS Lambda<br/>Alert evaluation]
    DLQ[Amazon SQS<br/>Evaluation DLQ]
    Topic[Amazon SNS]
    Subscriber[Opt-in subscribers]
    API[Amazon API Gateway<br/>HTTP API]
    Query[AWS Lambda<br/>Query service]
    CDN[Amazon CloudFront]
    Web[(Amazon S3<br/>Static dashboard)]
    User[Community user]
    CW[Amazon CloudWatch]

    Scheduler --> Ingest
    Ingest --> Source
    Ingest --> DB
    Ingest --> Bus
    Bus --> Evaluate
    Bus -. failed delivery after retries .-> DLQ
    Evaluate --> DB
    Evaluate --> Topic
    Topic --> Subscriber

    User -->|HTTPS| CDN
    CDN --> Web
    User -->|HTTPS| API
    API --> Query
    Query --> DB

    Ingest -. logs and metrics .-> CW
    Evaluate -. logs and metrics .-> CW
    Query -. logs and metrics .-> CW
```

### Request and event flow

1. EventBridge Scheduler invokes the ingestion Lambda at a configurable interval.
2. The function requests current data from the external provider, validates the response, and stores a normalized observation in DynamoDB.
3. The function publishes an `ObservationRecorded` domain event to EventBridge.
4. EventBridge retries a failed target delivery up to two times within one hour, then preserves the undelivered event in an encrypted SQS dead-letter queue.
5. The evaluation Lambda applies versioned threshold rules and records any alert-state transition.
6. Amazon SNS notifies subscribers only when an alert opens, changes severity, or closes, reducing duplicate notifications.
7. The public dashboard retrieves current and historical data through a read-only HTTP API.

`ObservationRecorded` uses at-least-once delivery. If DynamoDB confirms that the observation already exists during a retry, ingestion publishes the event again so a previous EventBridge failure cannot permanently lose it. The evaluator is responsible for ignoring duplicate observation identities and preventing duplicate notifications.

SNS messages are emitted only for committed `OPENED`, `SEVERITY_CHANGED`, and `CLOSED` transitions. Each message includes the location, alert type, severity, observation time, and informational-use disclaimer. Subscriber contact details are managed by SNS subscription confirmation and are never written to the application table. SNS Standard delivery is at least once, so subscribers can still receive a rare delivery duplicate even though unchanged observations do not generate new messages.

## Why These Services?

| Service | Responsibility | Rationale |
|---|---|---|
| EventBridge Scheduler | Periodic ingestion | Managed scheduling without continuously running compute |
| AWS Lambda | Ingestion, evaluation, and queries | Pay-per-use execution suitable for a low-volume MVP |
| DynamoDB | Observations and alert states | Serverless persistence with predictable key-based access patterns |
| EventBridge | Domain-event routing | Decouples ingestion from alert evaluation and future consumers |
| API Gateway HTTP API | Public read-only endpoints | Managed HTTPS endpoint with throttling and lower complexity than operating a server |
| SNS | Opt-in notifications | Managed fan-out and subscription confirmation |
| S3 and CloudFront | Static web application | Low-maintenance hosting, caching, HTTPS, and private S3 origin access |
| CloudWatch | Logs, metrics, dashboards, and alarms | Centralized operational visibility across serverless components |
| AWS SAM | Infrastructure as Code | Repeatable serverless deployments using a small declarative template |

The architecture will be revised when implementation evidence exposes different requirements. Services are selected to solve specific responsibilities, not to maximize the number of AWS products used.

## Quality Attributes

### Cost efficiency

- Prefer on-demand, pay-per-request services.
- Cache static assets at the edge.
- Apply DynamoDB expiration to observations that no longer require detailed retention.
- Configure AWS Budgets before deploying shared or recurring resources.
- Document an AWS Pricing Calculator estimate before the first public release.

### Reliability

- Validate external responses before persistence.
- Make scheduled ingestion idempotent using location and observation time.
- Use bounded retries and encrypted dead-letter handling for failed event deliveries.
- Preserve the last successful observation while clearly displaying its timestamp and freshness.
- Notify operators when ingestion has not succeeded within the expected interval.

### Security

- Block all public access to the S3 bucket and use CloudFront Origin Access Control.
- Expose only read operations through the public API.
- Apply least-privilege IAM policies to every Lambda function.
- Enforce HTTPS, API throttling, log retention, and dependency scanning.
- Avoid storing subscriber contact details in the application database; SNS manages confirmed subscriptions.
- Store no AWS credentials or secrets in the repository.

### Performance

- Design API access around known DynamoDB partition and sort keys.
- Return bounded time ranges rather than unbounded observation histories.
- Cache static assets through CloudFront.
- Measure API latency before introducing additional caching.

### Observability

- Emit structured JSON logs with correlation identifiers.
- Track ingestion success, provider errors, stale data, alert transitions, and API failures.
- Create CloudWatch alarms for repeated ingestion failures and Lambda errors.
- Maintain a small operational dashboard for system health.

## Data Model — Initial Proposal

A single DynamoDB table is proposed for the MVP:

```text
PK                       SK                              Entity
LOCATION#LIMA_CORPAC     OBSERVATION#<ISO-8601>          Environmental observation
LOCATION#LIMA_CORPAC     ALERT#<OBSERVED_AT>#<TYPE>      Alert transition history
LOCATION#LIMA_CORPAC     STATE#<TYPE>                    Current alert state
```

The model supports the initial access patterns:

- Get the latest observation for a location.
- List observations for a bounded time range.
- Get current alert states.
- List recent alert transitions.

The design will not be generalized for multiple locations until that requirement is implemented.

## Data Source and Responsible Use

The MVP plans to use the [Open-Meteo Weather API](https://open-meteo.com/en/docs) and [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api). Provider attribution, licensing, request limits, and usage conditions will be reviewed before public deployment.

Alert thresholds will be configurable and documented with their sources. AyniAlert will display measurement timestamps and data freshness so users can distinguish current information from stale data.

### Development alert thresholds — ruleset version 1

The provider and the interpretation policy have separate responsibilities. Open-Meteo supplies normalized measurements; the following sources support how enabled measurements are grouped. `ADVISORY`, `HIGH`, and `CRITICAL` are informational AyniAlert labels, not medical diagnoses or official warning levels.

| Measurement | AyniAlert mapping | Status | Rationale and source |
|---|---|---|---|
| Apparent temperature | No severity bands | `NOT_CONFIGURED` | Open-Meteo defines the measurement, but no locally applicable risk thresholds have been approved. The value is still collected and displayed; this status must not be interpreted as safe. [Open-Meteo Weather API](https://open-meteo.com/en/docs) |
| UV index | `< 3`: inactive; `3–<8`: `ADVISORY`; `8+`: `HIGH` | Enabled | WHO recommends protection from UV index 3 and groups values as 3–7 and 8+. [WHO UV index guidance](https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-%28uv%29-index) |
| US AQI | `≤ 100`: inactive; `101–150`: `ADVISORY`; `151–200`: `HIGH`; `201+`: `CRITICAL` | Enabled | AirNow categorizes 101–150 as unhealthy for sensitive groups, 151–200 as unhealthy, and 201+ as very unhealthy or hazardous. [AirNow AQI basics](https://www.airnow.gov/aqi/aqi-basics/) |

The versioned configuration lives in `backend/src/ayni_alert/domain/default_alert_rules.py`. Threshold changes require a new rule version, review, tests, and deployment; they are never hidden inside Lambda handlers.

> **Disclaimer:** AyniAlert is an educational project and an informational tool. It is not a medical device, an official warning system, or a substitute for guidance from health authorities, emergency services, SENAMHI, or other official agencies.

## Technology Stack

- **Cloud:** AWS
- **Infrastructure as Code:** AWS SAM
- **Backend:** Python 3.13 on AWS Lambda
- **API:** Amazon API Gateway HTTP API
- **Database:** Amazon DynamoDB
- **Frontend:** Vue 3 and TypeScript
- **Testing:** pytest, Vitest, and Playwright
- **CI/CD:** GitHub Actions with short-lived AWS credentials through OpenID Connect
- **Development workflow:** Kiro specs, Git, and Architecture Decision Records

## Planned Repository Structure

```text
.
├── .github/workflows/       # Validation and deployment workflows
├── .kiro/specs/ayni-alert/  # Requirements, design, and implementation tasks
├── backend/
│   ├── functions/           # Lambda handlers and application modules
│   └── tests/
├── frontend/                # Public Vue dashboard
├── infrastructure/          # AWS SAM templates and deployment configuration
├── docs/
│   ├── adr/                 # Architecture Decision Records
│   └── diagrams/            # Exported architecture diagrams
└── README.md
```

## Delivery Roadmap

### Phase 1 — Walking skeleton

- Define requirements and acceptance criteria in Kiro.
- Create the SAM application and least-privilege IAM roles.
- Ingest and persist one real observation on a schedule.
- Expose a health endpoint and the latest observation.

### Phase 2 — Functional MVP

- Implement threshold evaluation and alert-state transitions.
- Add the Vue dashboard and recent observation history.
- Add opt-in SNS notifications.
- Add structured logs, alarms, tests, and a cost estimate.
- Publish the first deployment and document verification evidence.

### Phase 3 — Evidence-driven improvements

- Gather usability feedback.
- Add locations only when supported by a validated use case.
- Review the workload against the AWS Well-Architected Framework.
- Evaluate whether forecasting or generated summaries add measurable value.

## Architecture Decisions

Architecture decisions will be recorded under `docs/adr/`. Initial decisions to document include:

- ADR-001: Use a serverless architecture for the MVP.
- ADR-002: Use DynamoDB with explicit access patterns.
- ADR-003: Separate ingestion from alert evaluation using domain events.
- ADR-004: Use AWS SAM for repeatable deployments.
- ADR-005: Keep generative AI outside the MVP.

## Kiro-Assisted Development

Kiro will be used to refine requirements, design documents, implementation tasks, and code. Generated output will be reviewed, tested, and owned by the project author. AI assistance does not replace architectural reasoning, security review, or validation against deployed behavior.

## Success Criteria for the First Release

The first release will be considered functional when:

- Infrastructure can be deployed reproducibly from the repository.
- A scheduled execution stores valid environmental observations.
- The public API returns the latest observation and its freshness.
- The dashboard displays real data from the deployed API.
- One configured threshold can open and close an alert without duplicate notifications.
- Automated tests pass and operational alarms are configured.
- The README links to deployment evidence and an architecture-cost estimate.

## Author

**Manuel Malpartida Huamán**  
Systems Engineering student at the University of Lima  
[LinkedIn](https://www.linkedin.com/in/manuel-malpartida) · [GitHub](https://github.com/ManuelMH16)

## License

License selection is pending before the first public release.
