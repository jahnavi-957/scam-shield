# Cost Plan

Budget: **about $100 of AWS credits for the whole team**. This plan states how we stay inside that envelope, what each planned resource costs, and how it is shut down.

> Local development (M0–M2) costs **$0** — everything runs in Docker Compose on a laptop.

## 1. Budget strategy

1. **Do not run AWS between sessions.** A "running" stack accrues charges even while unused. We create resources for a test window, use them, and tear them down. The `docs` teardown runbook (M12 deliverable) formalizes this.
2. **No optional-cost services for "show".** No NAT Gateway, no Multi-AZ, no continuous ALB, no provisioned Bedrock/Textract spend.
3. **Smallest compliant instance sizes.** The faculty requirement is EC2/containers — a `t3.micro` or `t3.small` satisfies it.
4. **Watch spend weekly** via AWS Budget alerts (M10) and a shared cost check-in.
5. Every resource we create gets tags (`Project=ScamShield, Environment=dev, Owner=team, Purpose=…`) and an expected lifetime.

## 2. Planned resource estimates (on-demand prices, approximate)

Prices are as-honest-as-possible estimates for a single region; verify on AWS pricing pages before deploying. The goal is a realistic **month-inclusive demo**, not precision.

| Resource | Config | Approx rate | Notes |
|---|---|---|---|
| EC2 instance | `t3.micro` (2 vCPU, 1 GiB RAM) + 8 GB gp3 EBS | ~$0.0116/hr → **~$8.4/mo** if running 24/7 | Run only during demo windows |
| RDS PostgreSQL | `db.t3.micro`, single-AZ, 20 GB gp3 + backups | ~$0.017/hr → **~$12.3/mo** if 24/7 | pgvector extension (free, same instance) |
| Application Load Balancer | 1 ALB + 1 LCU baseline | ~$0.0225/hr → **~$16.2/mo** | **Created only for deployment/testing weeks, then destroyed** |
| S3 | screenshots, dev volume | pennies | Private, lifecycle rules to expire objects |
| SQS | dev volume | pennies | Standard queue + DLQ |
| CloudWatch | standard metrics, ~1 custom metric, logs, 1-2 alarms | ~$1–3/mo | Keep log data volume small |
| ECR | image storage | ~$1/mo | Delete stale images |
| SSM Parameter Store | 5–10 params | ~$0–0.85/mo | Free tiers mostly cover usage |
| NAT Gateway | — | **$0 (avoided)** | No always-on NAT; revisited in M3 with alternatives |

### Realistic running scenarios
- **M1–M2 (local):** $0.
- **Milestone test window (a few hours, then teardown):** well under $1 per window.
- **Worst case — everything on for a month:** ~$40–45. **Budget rule:** keep total under the $100 envelope including headroom; prefer weekend-only full-stack runs.

## 3. Deliberately avoided (and why)

| Avoided | Why |
|---|---|
| NAT Gateway ($32+/mo + data) | Private subnets don't need permanent outbound internet; inbound routing only. M3 reopens this with alternatives if outbound is actually needed. |
| Multi-AZ RDS | Doubles DB cost; single-AZ acceptable for the course demo. |
| >1 running EC2 (ASG max 2) | ASG min=desired=1; max=2 only to *demonstrate* replacement, then scaled back. |
| Textract | OCR falls back to an open-source engine (M6 decision) unless faculty requires AWS service; Tesseract costs $0. |
| Bedrock on every request | Explanation-only, late milestone, bounded usage, fallback template when unavailable. |
| Fully serverless app | Faculty forbids it; also avoids per-request costs. |

## 4. Verification of spend

- **AWS Budgets** alarm at, e.g., 50% and 90% of $100 (M10 via Terraform).
- **CloudWatch billing metrics** watched during test windows.
- After each AWS milestone: record actual spend in `docs/evidence/` (M12) and compare to this plan.

## 5. Cost checklist before creating any AWS resource (from master spec)

1. What does it cost?
2. Why do we need it?
3. Is it mandatory?
4. Is there a cheaper alternative?
5. How do we shut it down afterwards?

No AWS resource is created until this checklist is answered in the relevant milestone's plan and approved.