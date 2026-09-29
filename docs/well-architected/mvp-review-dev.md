# AWS Well-Architected MVP review — dev

## Scope and result

- Review date: 2026-09-29
- Environment: `dev`
- Region: `us-east-1`
- Workload: AyniAlert serverless environmental-alert MVP
- Evidence: version-controlled code, SAM and OIDC templates, workflows, tests, the deployed API and dashboard, and the performance and cost records linked below

**Result:** suitable as a development MVP, but not production-ready. The workload has strong serverless foundations and proportionate controls for its current scale. Two correctness gaps require priority follow-up: the evaluator's SAM role does not declare the DynamoDB transaction permission used by its code, and notification publication is not atomic with the committed alert transition.

This review does not claim a formal AWS Well-Architected Tool assessment or independent verification of every resource in the AWS account. Some resources were created manually and must be reconciled before the SAM template can be treated as proof of deployed state.

## Evidence classification

- **Implemented:** directly verifiable in source code, tests, workflows, or infrastructure templates.
- **Measured:** produced by a documented experiment; raw AWS telemetry is not exported with every result.
- **Observed:** verified against the public `dev` endpoints or documented from AWS Console checks.
- **Estimated:** based on stated traffic and pricing assumptions.

Key evidence:

- [`template.yaml`](../../template.yaml) — desired serverless infrastructure and permissions.
- [`infra/github-oidc.yaml`](../../infra/github-oidc.yaml) — deployment identity and scoped permissions.
- [Performance evidence](../performance/mvp-latency-dev.md) — scenario, optimization, and latency results.
- [Cost evidence](../cost/mvp-cost-estimate-dev.md) — assumptions, estimate, Cost Explorer comparison, and budget.
- [OpenAPI contract](../api/openapi.json) — public read-only interface.
- [Requirements](../../.kiro/specs/ayni-alert/requirements.md) and [design](../../.kiro/specs/ayni-alert/design.md) — intended quality attributes and decisions.

## Pillar assessment

### 1. Operational Excellence — needs follow-up

**Strengths**

- Requirements, design, and tasks provide traceability from quality goals to implementation.
- CI checks pytest, Ruff, SAM linting, TypeScript, Vitest, Playwright, dependency audit, and the frontend production compilation.
- Lambda handlers emit structured logs with correlation identifiers, while log retention is explicitly limited to 14 days.
- Ingestion publishes success, failure, freshness, and observation-age metrics. Failure and missing-heartbeat alarms address the workload's primary operational risk.
- Performance and cost checks use documented assumptions and reproducible commands rather than unsupported claims.

**Risks**

- The deployment workflow validates SAM but updates Lambda code and S3 objects directly. IAM, alarms, queues, API configuration, and other infrastructure changes are not applied by that workflow.
- Sequential Lambda and frontend updates are not an atomic release and have no automated rollback or post-deployment smoke test.
- There is no alarm for messages in the evaluation DLQ and no concise incident/redrive runbook.
- Observability is strongest for ingestion; evaluator failures, notification publication, API 5xx responses, throttles, and latency lack equivalent operational signals.

**Follow-up**

1. Reconcile manual resources and make SAM/CloudFormation the source of truth for application infrastructure.
2. Add deployed smoke tests and release metadata to the deployment workflow.
3. Add a DLQ alarm and a short runbook for stale data, failed evaluation, redrive, and rollback.
4. Add only decision-driving signals: evaluator errors, notification failures, API 5xx/throttles, and public-read latency.

### 2. Security — needs one priority correction

**Strengths**

- GitHub deploys through short-lived OIDC credentials. The trust policy is restricted to the `dev` environment and immutable repository identity, and the deployment policy names specific resources.
- The S3 origin blocks public access, uses encryption and versioning, and is readable only through CloudFront Origin Access Control.
- The public API exposes only throttled `GET` operations, uses origin-specific CORS, validates location and query input, and returns stable errors without internal details.
- Lambda responsibilities use separate roles; application storage does not contain SNS subscriber contact details.
- DynamoDB and SQS encryption are enabled, and no application secrets or AWS credentials are required by local tests.

**Priority gap — evaluator IAM mismatch**

`DynamoAlertRepository.compare_and_swap` calls `dynamodb:TransactWriteItems`, but `EvaluationFunction` grants `dynamodb:GetItem` and `dynamodb:PutItem`. A role created strictly from the current template cannot authorize the transaction. The deployed role may have been adjusted manually, but that would be configuration drift rather than reproducible least privilege.

**Additional risks**

- GitHub Actions use mutable major-version tags, and Python dependencies have no vulnerability audit in CI.
- CloudFront does not define an application-specific response headers policy for CSP, HSTS, anti-framing, referrer policy, and MIME sniffing protection.

**Follow-up**

1. Before the next infrastructure deployment, replace the unused evaluator `PutItem` permission with `TransactWriteItems`, retain `GetItem`, and add a template-level regression test.
2. Pin third-party Actions to reviewed commit SHAs and add a lightweight Python dependency audit.
3. Add and test a CloudFront response headers policy appropriate for the static Vue application and API origin.

### 3. Reliability — needs one priority design decision

**Strengths**

- Observation identity and conditional writes make ingestion idempotent.
- Persisted observations are republished after duplicate writes, preventing an earlier EventBridge failure from permanently suppressing evaluation.
- Evaluation uses a timestamp watermark, consistent state reads, optimistic revision checks, and transactional state/history writes to tolerate duplicate and out-of-order delivery.
- Provider responses are validated for schema, units, timestamps, ranges, finite numbers, and completeness before persistence.
- EventBridge retries are bounded and failed evaluator delivery goes to an encrypted 14-day SQS DLQ.
- The API preserves the last valid observation while exposing freshness, and history requests are bounded and paginated.

**Priority gap — notification loss window**

The evaluator commits the alert transition in DynamoDB and publishes SNS afterward. If SNS publication fails, EventBridge retries the observation; the committed timestamp watermark then classifies it as already processed, so the notification is not reconstructed. Application-level duplicate suppression therefore creates a possible permanent notification loss.

**Additional risks**

- The DLQ has no alarm or documented redrive procedure.
- DynamoDB lacks deletion retention and point-in-time recovery. Omitting PITR is acceptable for disposable `dev`, but accidental stack deletion is not explicitly guarded.
- Lambda `$LATEST` and S3 deployment have no verified joint rollback procedure.

**Follow-up**

1. Choose explicitly between best-effort notifications and reliable delivery. Reliable delivery should use a transactional outbox item written with the alert transition and processed idempotently, for example through DynamoDB Streams.
2. Until that design is implemented, document the best-effort limitation and alarm on publication failures.
3. Alarm when the DLQ contains a message and document inspection and redrive.
4. Add `DeletionPolicy` and `UpdateReplacePolicy` retention to DynamoDB; enable PITR before using a non-disposable environment.

### 4. Performance Efficiency — meets the MVP target

**Strengths**

- DynamoDB access uses partition/sort keys, bounded limits, and no public-request scans.
- SDK resources and connection pools are reused across warm Lambda invocations.
- Read functions were selectively raised to 256 MB after measurement instead of increasing every function.
- CloudFront enables compression, HTTP/2 and HTTP/3, while hashed frontend assets receive immutable long-term caching.
- The measured server p95 was 57.03 ms for Latest and 123.66 ms for History, below the 2,000 ms target. The combined external p95 was 425.71 ms with no errors in the post-optimization run.

**Risks**

- Thirty samples per route are enough for an MVP check but weak for tail characterization; maxima remained above two seconds.
- The load generator is closed-loop, so achieved request rate can decrease when responses slow down.
- API latency, integration latency, and throttles are not continuously monitored.
- The API disables caching even though source observations normally change hourly. That is acceptable at current traffic but may become wasteful.

**Follow-up**

1. Preserve raw results and run several short measurements with achieved rate, API Gateway latency, Lambda duration, and p99.
2. Add minimal native latency/error alarms before introducing more infrastructure.
3. Consider ETag or a short cache only after traffic demonstrates a need; do not add provisioned concurrency or a cache service prematurely.

### 5. Cost Optimization — meets the MVP target with housekeeping gaps

**Strengths**

- Lambda, HTTP API, EventBridge, DynamoDB on-demand, SNS, SQS, S3, and CloudFront align cost with low request volume.
- Hourly ingestion, transition-only notifications, 30-day observation TTL, 14-day logs, and bounded history limit recurring work and storage.
- Static assets are edge-cached and the design avoids always-on compute, NAT Gateway, RDS, and unnecessary AI services.
- The documented estimate is USD 1.50/month under stated assumptions, initial Cost Explorer usage was USD 0.00, and an account-wide USD 5 budget was observed in `OK`.

**Risks**

- S3 versioning plus `sync --delete` has no lifecycle rule for noncurrent objects or delete markers.
- The estimate has no 10× sensitivity case or scenario without free allowances.
- Cost-allocation tagging and its activation are not completely evidenced, while the old setup task remains open.
- Alert-transition history has no explicit retention policy.

**Follow-up**

1. Expire noncurrent dashboard versions after a proportionate rollback window and abort incomplete multipart uploads.
2. Add base, 10×, and without-free-allowance scenarios to the next cost review.
3. Reconcile the setup checklist with actual budget and cost-tag evidence.
4. Decide whether transition history is permanent or assign it a longer TTL than observations.

### 6. Sustainability — good architectural fit, not yet explicit

**Strengths**

- Request-based managed services avoid continuously idle compute.
- One hourly ingestion matches the two-hour freshness policy without excessive polling.
- TTL, log retention, compression, edge caching, bounded responses, and idempotency reduce unnecessary storage, transfer, and repeated work.
- The frontend performs two initial reads and user-triggered retries rather than continuous background polling.

**Risks**

- Sustainability is not currently stated as a quality attribute or reviewed with measurable proxy indicators.
- Noncurrent S3 versions and transition history can grow without a retention bound.
- `x86_64`, `us-east-1`, and CloudFront `PriceClass_100` are reasonable defaults but have not been compared against alternatives with representative Lima traffic.

**Follow-up**

1. Adopt simple proxies rather than inventing carbon numbers: retained bytes, transferred bytes per visit, Lambda duration per workflow, and avoided polling.
2. Apply the S3 and data-retention housekeeping above.
3. Benchmark `arm64` or another region only when representative traffic makes the comparison meaningful.

## Prioritized improvement register

| Priority | Follow-up | Why now | Completion evidence |
|---|---|---|---|
| P0 | Grant evaluator `dynamodb:TransactWriteItems` and verify the deployed role matches SAM | Current desired-state IAM is incompatible with the repository implementation | Template regression test, successful SAM deployment, evaluator transition smoke test |
| P0 | Decide and document notification delivery semantics; implement an outbox if reliable delivery is required | Current commit-then-publish flow can permanently lose a notification | Failure-injection test proving retry/recovery, or an explicit accepted best-effort requirement |
| P1 | Reconcile manual resources and deploy infrastructure through SAM/CloudFormation | Eliminates drift and partial configuration releases | Stack inventory, import/recreation record, successful changeset deployment |
| P1 | Add DLQ/evaluator/API alarms and a small runbook | Existing failure storage is not actionable without detection and response | Alarm definitions plus tested runbook steps |
| P1 | Add post-deployment smoke tests and rollback metadata | A successful upload does not prove a healthy release | Workflow summary with commit, outputs, smoke results, and rollback reference |
| P2 | Add CloudFront security headers and supply-chain hardening | Proportionate hardening for a public endpoint | Header verification, pinned Actions, Python dependency audit |
| P2 | Add S3 lifecycle, retention decisions, and cost sensitivity | Prevents silent storage growth and improves forecast quality | Lifecycle IaC and updated cost evidence |
| P2 | Expand performance evidence and sustainability proxies | Improves decisions without premature infrastructure | Raw measurements and periodic review record |

## Decisions intentionally deferred

The current evidence does **not** justify multi-region deployment, provisioned concurrency, ElastiCache, a dedicated APM platform, a larger compute tier, or generative AI. These options add cost and operational surface without addressing the highest risks identified above.

## Review conclusion

AyniAlert demonstrates the Well-Architected principles expected from a serious development MVP: explicit quality goals, managed request-based services, least-privilege intent, defensive validation, idempotency, freshness handling, bounded queries, monitoring, measured performance, and cost controls.

The next improvement should not be another AWS service. It should be closing the gap between desired infrastructure, deployed infrastructure, and delivery semantics. Correcting evaluator IAM, deciding notification reliability, and making failure handling actionable will provide more value than premature scaling work.
