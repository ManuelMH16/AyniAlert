# MVP API latency evidence — dev

## Scope

- Date: 2026-09-29
- Region: `us-east-1`
- API: `ayni-alert-http-dev`
- Stage: `dev`
- Location: `LIMA_CORPAC`
- Target: p95 server response time below 2,000 ms at expected MVP load

The controlled scenario represents one active dashboard session repeatedly loading its two read
resources. Each of 30 iterations called Latest and History concurrently, with a two-second interval:

- 60 total requests
- 1 request per second aggregate target rate
- Maximum concurrency of 2
- History page limit of 24
- API throttling configured at rate 5 and burst 10

The scenario is reproducible with:

```bash
.venv/bin/python scripts/measure_api_latency.py \
  --base-url https://sjf63cndec.execute-api.us-east-1.amazonaws.com/dev
```

## Initial measurement

The first run returned 56 of 60 successful client responses, with four five-second client timeouts
and a combined p95 of 5,197.54 ms. API Gateway reported peak Latency of 7,308.94 ms and
IntegrationLatency of 7,305.75 ms, with no 4xx or 5xx responses. Lambda REPORT entries confirmed
four internal execution outliers between 6,061.56 and 7,173.08 ms; initialization contributed only
113.24–140.10 ms.

An immediate identical repetition returned 60 of 60 successful responses and a combined
client-observed p95 of 930.83 ms. Although this met the p95 target, the first run demonstrated an
avoidable performance risk rather than a client-network failure.

## Optimization

- Reused one lazily initialized DynamoDB SDK resource and connection pool within each warm Lambda
  execution environment instead of recreating it for every request.
- Increased only Latest and History from 128 MB to 256 MB, providing more CPU and network capacity
  to the latency-sensitive read path.
- Preserved the API contract, key-based DynamoDB queries, throttling, and least-privilege policies.

## Post-optimization measurement

### External client

| Route | Requests | Errors | p50 | p95 | Maximum |
|---|---:|---:|---:|---:|---:|
| Latest | 30 | 0 | 344.36 ms | 381.32 ms | 3,449.40 ms |
| History | 30 | 0 | 334.24 ms | 431.22 ms | 2,416.75 ms |
| Combined | 60 | 0 | 342.13 ms | 425.71 ms | 3,449.40 ms |

Compared with the stable pre-optimization repetition, combined client p50 decreased by about 52%
and p95 decreased by about 54%.

### Lambda server duration

CloudWatch Logs Insights calculated duration percentiles from the 30 REPORT records for each
function during the post-deployment run:

| Function | Requests | p50 | p95 | Maximum | Maximum init duration |
|---|---:|---:|---:|---:|---:|
| Latest | 30 | 38.08 ms | 57.03 ms | 2,991.82 ms | 130.53 ms |
| History | 30 | 26.50 ms | 123.66 ms | 1,945.52 ms | 90.67 ms |

## Conclusion

Both read functions satisfy the p95 server-response target by a wide margin under the defined MVP
load, and all post-optimization requests completed successfully. The isolated Latest maximum above
two seconds does not violate the percentile target, but it remains a first-invocation risk worth
tracking. Provisioned concurrency is intentionally not enabled for the MVP because its recurring
cost is not justified by the measured p95; operational metrics should be reviewed if traffic or
tail-latency requirements increase.
