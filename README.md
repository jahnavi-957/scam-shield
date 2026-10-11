# Scam Shield

AI-powered fraud detection system for UPI, SMS, WhatsApp, and email scams. Scam Shield automatically ingests messages, classifies them using a fine-tuned deep learning model, extracts dangerous entities (UPI IDs, phone numbers, URLs), and matches them against a continuously growing shared "scam graph" so that once one person reports a scammer, everyone benefits.

---

## Problem

Scam messages — fake payment requests, phishing links, prize scams, loan fraud, impersonation — are reported in isolation today. The same scammer (same UPI ID, same phone number, same reworded message) hits hundreds of victims before anyone connects the dots. There's no shared, real-time system that recognizes "this exact scam pattern has already been reported."

## What Scam Shield Does

1. **Fetches** new messages automatically (via email polling, or manual paste/upload for the demo)
2. **Extracts** entities — UPI IDs, phone numbers, URLs — using regex/NLP
3. **Classifies** the message using a fine-tuned DistilBERT model (scam type + confidence)
4. **Embeds** the message using a sentence-transformer and checks it against previously reported scams for near-duplicate matches (catches reworded scams)
5. **Stores** the result in a shared database, incrementing report counts for recognized scammers
6. **Alerts** via SNS/CloudWatch when a pattern crosses a report threshold

---

## Architecture

```
                    ┌─────────────────┐
                    │   EventBridge    │ (scheduled trigger)
                    │   + Lambda       │
                    └────────┬─────────┘
                             │ polls inbox
                             ▼
┌──────────┐        ┌─────────────────┐        ┌──────────┐
│ Frontend │───────▶│   EC2 (Docker)   │───────▶│   RDS    │
│ (S3/EC2) │  HTTP  │   FastAPI app    │  SQL   │PostgreSQL│
└──────────┘        │                  │        └──────────┘
                     │  - Entity extract│
                     │  - DistilBERT    │
                     │  - Embeddings    │
                     └────────┬─────────┘
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
              ┌─────┐    ┌─────────┐  ┌──────────┐
              │ S3  │    │CloudWatch│  │   SNS    │
              │(OCR │    │ (alarms) │  │ (alerts) │
              │input)│   └──────────┘  └──────────┘
              └─────┘
```

All compute runs inside a custom VPC (public subnet for EC2, private subnet for RDS), with IAM least-privilege roles and secrets in SSM Parameter Store.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (or plain HTML/JS) |
| Backend | FastAPI (Python) |
| Classification model | DistilBERT, fine-tuned (HuggingFace `transformers`) |
| Embedding model | Sentence-transformers (`all-MiniLM-L6-v2`) |
| OCR (screenshot input) | Tesseract / AWS Textract |
| Database | PostgreSQL (AWS RDS) |
| Autonomous ingestion | Gmail API (OAuth, read-only) via scheduled Lambda + EventBridge |
| Infra as Code | Terraform |
| CI/CD | GitHub Actions |
| Monitoring | CloudWatch (logs, metrics, alarms) |
| Notifications | SNS |

---

## AWS Services Used

- **EC2** — hosts the Dockerized FastAPI app (non-serverless compute requirement)
- **VPC** — custom network: public/private subnets, IGW, route tables, security groups
- **RDS (PostgreSQL)** — stores messages, entities, embeddings, scam reports
- **S3** — stores uploaded screenshots for OCR
- **IAM** — least-privilege role attached to EC2
- **SSM Parameter Store** — DB credentials and secrets
- **CloudWatch** — logs, metrics, and alarm on report-rate spikes
- **SNS** — alert notifications when a scam pattern crosses threshold
- **Lambda + EventBridge** — scheduled email-inbox polling (supporting role only)
- **Terraform** — infrastructure as code
- **GitHub Actions** — CI/CD pipeline for build + deploy

---

## Project Structure

```
scamshield/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── extraction.py        # entity extraction (regex/NLP)
│   │   ├── classifier.py        # DistilBERT inference
│   │   ├── embeddings.py        # sentence-transformer + similarity matching
│   │   ├── db.py                 # RDS models/queries
│   │   └── alerts.py            # SNS publishing logic
│   ├── Dockerfile
│   └── requirements.txt
├── ml/
│   ├── scamshield_ml/       # importable ML package (extraction, classifier, embeddings, pipeline)
│   ├── prepare_dataset.py   # assembles + cleans + splits the dataset
│   ├── train_classifier.py  # DistilBERT fine-tuning (HF Trainer)
│   ├── dataset/             # labeled data (handwritten seeds + Kaggle datasets + generated splits)
│   ├── tests/               # pytest suite
│   ├── model/               # fine-tuned weights (generated)
│   └── evaluation.md        # metrics, confusion matrix, writeup (generated)
├── ingestion/
│   └── email_poller/            # Lambda function for scheduled email fetch
├── frontend/
│   └── ...                      # React app
├── infra/
│   └── terraform/                # VPC, EC2, RDS, IAM, SG definitions
├── .github/workflows/
│   └── deploy.yml                # CI/CD pipeline
└── README.md
```

---

## Setup

### Prerequisites
- AWS account (Free Tier eligible — new account recommended for credits)
- Terraform installed
- Docker installed
- Python 3.10+
- HuggingFace account (optional, for model hosting)

### 1. Clone and configure
```bash
git clone <repo-url>
cd scamshield
cp .env.example .env
# fill in DB credentials, AWS region, etc.
```

### 2. Provision infrastructure
```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```
This creates the VPC, EC2 instance, RDS instance, security groups, and IAM role.

### 3. Train the classifier (or use provided weights)
```bash
cd ml
jupyter notebook train_classifier.ipynb
```
Outputs a fine-tuned model saved to `ml/model/`, uploaded to S3 for the backend to pull at startup.

### 4. Build and deploy the backend
```bash
cd backend
docker build -t scamshield-backend .
# push to ECR or deploy via GitHub Actions
```

### 5. Configure email polling (optional, for autonomous fetch)
Set up Gmail API OAuth credentials, deploy the Lambda in `ingestion/email_poller/`, and attach the EventBridge schedule (e.g., every 5 minutes).

---

## How It Works — Example

**Input:** `"Congrats! You've won ₹50,000. Claim now by paying ₹500 fee to upi: fraud123@okaxis or click bit.ly/claim-prize"`

**Output:**
```json
{
  "is_scam": true,
  "scam_type": "fake_prize_scam",
  "confidence": 0.94,
  "entities_found": {
    "upi": "fraud123@okaxis",
    "url": "bit.ly/claim-prize"
  },
  "prior_reports": 12,
  "explanation": "This matches a known fake-prize scam pattern. The UPI ID has been reported 12 times in the past week."
}
```

If `prior_reports` crosses the alert threshold, an SNS notification fires automatically.

---

## Model Details

**Classifier:** DistilBERT fine-tuned on a labeled dataset of scam/non-scam messages (public SMS spam datasets + custom-labeled Indian scam examples covering UPI fraud, loan scams, prize scams, impersonation). Evaluated on accuracy, precision, recall, and F1-score (see `ml/evaluation.md`).

**Embedding model:** Pretrained sentence-transformer (`all-MiniLM-L6-v2`) used to detect near-duplicate scam messages via cosine similarity, catching reworded variants of the same scam.

---

## Cost

Designed to run within AWS Free Tier / new-account credits. Estimated monthly cost if left running continuously: **~$20–30** (EC2 t3.small + RDS t4g.micro + minor S3/SNS/CloudWatch usage). Resources should be stopped/deleted after demo use; see `infra/terraform/README.md` for teardown instructions.

---

## Known Limitations / Future Work

- Autonomous ingestion currently supports email only (Gmail API); SMS ingestion would require an Android companion app with user-granted `READ_SMS` permission
- No Auto Scaling / Load Balancer in the current (cost-optimized) setup — noted as a future improvement for production resilience
- Scam-type taxonomy currently covers 4–5 major categories; expandable with more labeled data

---

## Team

- [Jahnavi Shah] – [10700]
- [Tanish Ingole] – [10661]
- [Shreysh Nair] – [10680]

## License

MIT
