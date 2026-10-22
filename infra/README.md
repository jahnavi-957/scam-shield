# Infrastructure and least-privilege deployment notes

The local Compose stack uses MinIO and Postgres. It does not create AWS
resources. The production VPC, RDS, S3, EC2, ALB, and SSM deployment remains a
deferred infrastructure task and must be implemented with Terraform before a
public deployment.

## Runtime IAM policy

[`iam/ec2-runtime-policy.json`](./iam/ec2-runtime-policy.json) is the reviewed
starting policy for the EC2 application role. Replace the angle-bracket
placeholders with the real account, region, bucket, model version, and SNS
topic values at deployment time. It intentionally does **not** grant:

- `s3:*` on the whole bucket;
- `ssm:*` or access to unrelated parameter paths;
- `sns:*` on unrelated topics;
- RDS, EC2, IAM, or administrator permissions.

The model prefix must be immutable/versioned. The upload bucket must have Block
Public Access, default encryption, a private bucket policy, and a lifecycle
rule that expires abandoned `uploads/` objects. RDS must use
`publicly_accessible = false` and accept port 5432 only from the backend
security group.
