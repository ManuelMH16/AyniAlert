# AyniAlert Implementation Tasks

Tasks are ordered to produce a deployable vertical slice early. A task is complete only when its tests and documentation are included.

## Phase 0 — Local and AWS safety setup

- [ ] 0.1 Install and verify AWS CLI v2, AWS SAM CLI, and Docker.
- [ ] 0.2 Configure an AWS development profile without committing credentials.
- [ ] 0.3 Enable MFA for the AWS account and avoid using the root user for development.
- [ ] 0.4 Create an AWS Budget and project cost-allocation tags before recurring deployment.
- [ ] 0.5 Add `.gitignore`, Python tooling configuration, and documented local commands.

## Phase 1 — Walking skeleton

- [ ] 1.1 Create the AWS SAM template with an HTTP API, health Lambda, DynamoDB table, and explicit log retention.  
  _Requirements: REQ-7, REQ-8, REQ-11, REQ-12_
- [ ] 1.2 Implement `GET /health` with structured responses and correlation IDs.  
  _Requirements: REQ-7_
- [ ] 1.3 Create backend package boundaries for domain, application, adapters, and handlers.  
  _Requirements: REQ-12_
- [ ] 1.4 Add unit-test and lint configuration without requiring AWS credentials.  
  _Requirements: REQ-12_
- [ ] 1.5 Validate the SAM template and run backend unit tests locally.  
  _Requirements: REQ-12_
- [ ] 1.6 Deploy the walking skeleton to an isolated development stack and record the commit, region, endpoint, and verification result.  
  _Requirements: REQ-12_

## Phase 2 — Real observation ingestion

- [ ] 2.1 Define the observation domain model, validation errors, units, schema version, and deterministic identity.  
  _Requirements: REQ-1, REQ-9, REQ-12_
- [ ] 2.2 Implement the Open-Meteo adapter with explicit timeouts and fixture-based tests.  
  _Requirements: REQ-1, REQ-9_
- [ ] 2.3 Implement observation normalization that rejects partial or incompatible provider data.  
  _Requirements: REQ-1_
- [ ] 2.4 Implement the DynamoDB repository with conditional idempotent writes and 30-day TTL.  
  _Requirements: REQ-1, REQ-9, REQ-11_
- [ ] 2.5 Implement the ingestion use case and Lambda handler with structured logging.  
  _Requirements: REQ-1, REQ-7_
- [ ] 2.6 Add EventBridge Scheduler for hourly execution using neighborhood-level Corpac coordinates.  
  _Requirements: REQ-1, REQ-11_
- [ ] 2.7 Verify one real observation in the development table and document evidence without exposing credentials.  
  _Requirements: REQ-1, REQ-12_

## Phase 3 — Read-only conditions API

- [ ] 3.1 Implement the latest-observation key query and freshness calculation.  
  _Requirements: REQ-2, REQ-9, REQ-10_
- [ ] 3.2 Implement `GET /v1/locations/{locationId}/latest` with stable errors and unit metadata.  
  _Requirements: REQ-2_
- [ ] 3.3 Implement bounded history query and pagination.  
  _Requirements: REQ-3, REQ-10_
- [ ] 3.4 Implement `GET /v1/locations/{locationId}/history` parameter validation.  
  _Requirements: REQ-3_
- [ ] 3.5 Configure API throttling, CORS for the dashboard origin, and read-only IAM permissions.  
  _Requirements: REQ-8_
- [ ] 3.6 Add API contract and deployed smoke tests.  
  _Requirements: REQ-2, REQ-3, REQ-12_

## Phase 4 — Alert state transitions

- [ ] 4.1 Document the rationale and source for each enabled threshold.  
  _Requirements: REQ-4_
- [ ] 4.2 Implement versioned alert-rule configuration and pure domain evaluation.  
  _Requirements: REQ-4, REQ-12_
- [ ] 4.3 Add exhaustive tests for open, severity-change, close, unchanged, and duplicate-delivery cases.  
  _Requirements: REQ-4, REQ-12_
- [ ] 4.4 Publish `ObservationRecorded` events after successful new writes.  
  _Requirements: REQ-4_
- [ ] 4.5 Implement the evaluator Lambda and conditional DynamoDB state transition.  
  _Requirements: REQ-4, REQ-9_
- [ ] 4.6 Configure EventBridge retry behavior and an SQS dead-letter queue.  
  _Requirements: REQ-9_
- [ ] 4.7 Add SNS transition messages with subscription confirmation and no subscriber PII in DynamoDB.  
  _Requirements: REQ-5, REQ-8_

## Phase 5 — Public dashboard

- [ ] 5.1 Scaffold the Vue 3 TypeScript application and define API response types.  
  _Requirements: REQ-6, REQ-12_
- [ ] 5.2 Implement current-condition cards, units, timestamps, freshness, and alert states.  
  _Requirements: REQ-6_
- [ ] 5.3 Implement loading, stale, unavailable, and empty states.  
  _Requirements: REQ-6, REQ-9_
- [ ] 5.4 Add recent-history visualization with accessible text alternatives.  
  _Requirements: REQ-3, REQ-6_
- [ ] 5.5 Add attribution and informational-use disclaimer.  
  _Requirements: REQ-4, REQ-6_
- [ ] 5.6 Add responsive component tests and Playwright critical-path coverage.  
  _Requirements: REQ-6, REQ-12_
- [ ] 5.7 Deploy to a private S3 origin behind CloudFront Origin Access Control.  
  _Requirements: REQ-8_

## Phase 6 — Operations and release evidence

- [ ] 6.1 Add custom metrics and CloudWatch alarms for ingestion failure and stale data.  
  _Requirements: REQ-7, REQ-9_
- [ ] 6.2 Verify explicit log retention and least-privilege IAM policies.  
  _Requirements: REQ-7, REQ-8, REQ-11_
- [ ] 6.3 Measure API latency at expected MVP load and record results.  
  _Requirements: REQ-10_
- [ ] 6.4 Produce an AWS Pricing Calculator estimate and compare it with initial Cost Explorer data.  
  _Requirements: REQ-11_
- [ ] 6.5 Add GitHub Actions checks and OIDC-based deployment without long-lived AWS keys.  
  _Requirements: REQ-8, REQ-12_
- [ ] 6.6 Update README statuses, deployed URL, architecture evidence, limitations, and screenshots.  
  _Requirements: REQ-12_
- [ ] 6.7 Perform an MVP review against the AWS Well-Architected pillars and record follow-up items.
