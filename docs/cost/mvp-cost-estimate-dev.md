# MVP monthly cost evidence — dev

## Scope and assumptions

- Estimate date: 2026-09-29
- Primary AWS Region: `us-east-1`
- Dashboard audience: Peru
- Dashboard visits: 3,000 per month
- HTTP API requests: 6,000 per month
- Scheduled ingestions and evaluation events: 720 each per month
- CloudFront transfer: 1 GB and 15,000 HTTPS requests per month
- S3 Standard storage: 0.02 GB
- CloudWatch standard logs ingested: 0.10 GB per month
- Environmental and operational email notifications: 100 per month

The estimate intentionally uses conservative aggregate Lambda duration and DynamoDB request volumes.
It does not include EC2, RDS, NAT Gateway, generative AI, or other services absent from the
architecture.

## AWS Pricing Calculator estimate

Estimate: [AyniAlert MVP dev](https://calculator.aws/#/estimate?id=6fbd807df76c8e6006af856ecc02cc7c19e8dcbb)

| Service | Estimated monthly cost |
|---|---:|
| AWS Lambda | USD 0.00 |
| Amazon API Gateway | USD 0.01 |
| Amazon DynamoDB | USD 0.04 |
| Amazon S3 | USD 0.00 |
| Amazon CloudFront | USD 0.00 |
| Amazon EventBridge | USD 0.00 |
| Amazon SNS | USD 0.00 |
| Amazon CloudWatch | USD 1.45 |
| Amazon SQS | USD 0.00 |
| **Total** | **USD 1.50** |

Lambda was modeled with 8,160 monthly requests, 500 ms conservative aggregate duration, and
256 MB memory. DynamoDB was modeled with 30,000 reads, 5,000 writes, and 0.1 GB Standard table
storage. The write mix accounts for atomic alert-state transactions; the read mix accounts for
eventually consistent observation reads and strongly consistent alert-state reads.

The deployed CloudFront distribution uses the USD 0/month flat-rate Free plan rather than
pay-as-you-go pricing. Its current allowances include the CDN, core WAF and DDoS protection,
1 million requests, 100 GB data transfer, and 5 GB of S3 Standard storage credits. A separate AWS
WAF estimate is therefore intentionally excluded. See the
[official CloudFront pricing page](https://aws.amazon.com/cloudfront/pricing/).

CloudWatch is the principal conservative cost because the calculator's metric and log sections do
not apply every account-level Free Tier allowance. Effective charges can therefore remain below
the gross estimate while usage remains eligible.

## Actual cost comparison

AWS Cost Explorer was checked for 2026-09-01 through 2026-09-30 using monthly granularity,
unblended cost, and grouping by service without a Region filter.

| Measure | Amount |
|---|---:|
| Pricing Calculator monthly estimate | USD 1.50 |
| September month-to-date actual cost | USD 0.00 |
| Actual minus estimate | USD -1.50 |

S3, Lambda, X-Ray, API Gateway, DynamoDB, SNS, SQS, CloudWatch, CloudWatch Events, and data
transfer all displayed USD 0.00. No separate WAF charge appeared. This early low-volume result is
consistent with the active CloudFront Free plan and service-level free allowances; it does not
guarantee that future usage will remain free.

## Cost control

An account-wide recurring monthly AWS Budget named `ayni-alert-monthly-dev` is configured at
USD 5.00 with status `OK`:

- Notify the operational email when actual cost exceeds 80% (USD 4.00).
- Notify the operational email when forecasted cost exceeds 100% (USD 5.00).
- Do not automatically disable resources.

The budget is account-wide rather than tag-filtered so that untagged or global resources cannot
silently bypass the alert.
