# qstp-s3-notification

Python Lambda function for the **qstp** (ATP) project. Watches S3 uploads of test results and triggers GitHub Actions to generate Allure reports.

## AWS resource

| Property | Value |
|----------|-------|
| Function name | `qstp-s3-notification` |
| Region | `us-east-1` |
| Runtime | `python3.14` |
| Handler | `lambda_function.lambda_handler` |
| Memory / timeout | 128 MB / 3 s |
| IAM role | `eks-tech-lambda` |
| Recommended `cost-usage` tag | `qstp` |

**Cost reporting note:** the function currently has no `cost-usage` tag in AWS, so Lambda charges appear under **`untagged`** in the monthly cost report. Tag the function with `cost-usage=qstp` to attribute costs to the qstp project.

## Triggers

S3 object-created events on:

- `qstp-results`
- `qstp-consul`

## Behaviour

1. Receives S3 event for a new object under `Result/`.
2. Extracts directory `Result/<test-type>/YYYY-MM-DD/HH-MM-SS/`.
3. Skips `Report/` paths and non-matching keys.
4. Calls GitHub `repository_dispatch` with event type `s3-new-result-directory`.
5. Workflow [process-s3-report.yml](../../../.github/workflows/process-s3-report.yml) builds the Allure report.

## Environment variables

Configured in Lambda (never commit secrets to git):

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope for dispatch API |
| `GITHUB_REPO_OWNER` | Repository owner (e.g. `Netcracker`) |
| `GITHUB_REPO_NAME` | Repository name (e.g. `qubership-terraform-hub`) |

## Deploy / update

```bash
cd aws-cost-reports/lambda/qstp-s3-notification
zip -j function.zip lambda_function.py
aws lambda update-function-code \
  --function-name qstp-s3-notification \
  --zip-file fileb://function.zip
```

Optional — align cost attribution:

```bash
aws lambda tag-resource \
  --resource "arn:aws:lambda:us-east-1:442426885383:function:qstp-s3-notification" \
  --tags cost-usage=qstp
```

## Owner

Denis Arychkov (qstp / ATP)
