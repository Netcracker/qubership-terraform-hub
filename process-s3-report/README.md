# S3 Report Processor Workflow

## Overview

The `process-s3-report.yml` workflow automates the processing of reports stored in Amazon S3. It triggers automatically when new report files are uploaded to a specified S3 bucket, processes them, and stores the results back in S3 with additional metadata.

## Workflow Trigger

This workflow is triggered by the `s3:ObjectCreated:*` event via Amazon EventBridge, which monitors a specific S3 bucket for new file uploads.

## Workflow Structure

### Prerequisites

Before using this workflow, ensure you have configured:
1. **AWS Credentials** in GitHub Secrets:
    - `AWS_ACCESS_KEY_ID`
    - `AWS_SECRET_ACCESS_KEY`
    - `AWS_REGION` (default: `us-east-1`)

2. **S3 Bucket Configuration**:
    - Source bucket for incoming reports
    - Destination bucket for processed results
    - Appropriate IAM permissions for read/write operations

### Jobs

#### 1. **process-report**
The main job that handles report processing:

**Environment Variables:**
- `AWS_REGION`: AWS region (defaults to GitHub secret or `us-east-1`)
- `SOURCE_BUCKET`: Bucket containing incoming reports
- `DESTINATION_BUCKET`: Bucket for processed results
- `REPORT_TYPE`: Type of report being processed

**Steps:**
1. **Checkout repository**: Retrieves the workflow code and processing scripts
2. **Configure AWS credentials**: Sets up AWS authentication using GitHub secrets
3. **Download report from S3**: Fetches the newly uploaded report file
4. **Process report**: Executes the report processing logic
    - Extracts relevant data
    - Transforms/aggregates as needed
    - Validates report contents
5. **Upload processed results**: Stores processed data back to S3
6. **Cleanup**: Removes temporary files
7. **Notification**: Sends success/failure notifications

## Input Parameters

The workflow accepts the following inputs via the S3 event metadata:

| Parameter | Description | Required |
|-----------|-------------|----------|
| `bucket` | S3 bucket name where report was uploaded | Yes |
| `key` | S3 object key (file path) of the report | Yes |
| `report-format` | Format of the report (CSV, JSON, XML, etc.) | No |
| `process-type` | Type of processing to apply | No |

## Output

The workflow produces:
1. **Processed files** in the destination S3 bucket with naming convention: `processed/{original_filename}_{timestamp}.{format}`
2. **Metadata file** containing processing details: `metadata/{original_filename}_metadata.json`
3. **Logs** in GitHub Actions for debugging and monitoring

## Metadata File Structure

```json
{
  "original_file": "s3://bucket-name/path/to/report.csv",
  "processed_file": "s3://destination-bucket/processed/report_20240123_142356.csv",
  "process_timestamp": "2024-01-23T14:23:56Z",
  "records_processed": 1500,
  "processing_duration_seconds": 45.2,
  "status": "SUCCESS",
  "error_message": null
}
```
## Usage

### Manual Execution
1. Navigate to your repository's Actions tab
2. Select "Process S3 Report" workflow
3. Click "Run workflow" button
4. (Optional) Provide custom input parameters if configured

### Scheduled Execution
The workflow runs automatically every day at midnight UTC (00:00). No manual intervention required.

### Customization Options

#### 1. Modify Schedule
Edit the cron schedule in the workflow file:

on:
schedule:
- cron: '0 0 * * *'  # Change to your preferred schedule

Common cron patterns:
- '0 * * * *' - Every hour
- '0 9-17 * * 1-5' - Weekdays 9 AM to 5 PM
- '0 0 * * 0' - Every Sunday at midnight

#### 2. Add Input Parameters
Extend the workflow to accept custom inputs:

on:
workflow_dispatch:
inputs:
report_type:
description: 'Type of report to process'
required: false
default: 'daily'

## Workflow Steps Breakdown

### 1. Checkout Code
- uses: actions/checkout@v3

Clones the repository to access Python scripts and configuration files.

### 2. Python Setup
- uses: actions/setup-python@v4
  with:
  python-version: '3.9'

Configures Python environment with specified version.

### 3. Install Dependencies
- name: Install Python dependencies
  run: pip install -r requirements.txt

Installs required Python packages from requirements.txt.

### 4. AWS Authentication
- uses: aws-actions/configure-aws-credentials@v1
  with:
  aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
  aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  aws-region: ${{ secrets.AWS_DEFAULT_REGION }}

Configures AWS credentials securely using GitHub Secrets.

### 5. Process S3 Report
- name: Process S3 report
  run: python scripts/process_s3_report.py
  env:
  S3_REPORT_BUCKET: ${{ secrets.S3_REPORT_BUCKET }}
  S3_REPORT_PATH: ${{ secrets.S3_REPORT_PATH }}

Executes the main Python script with environment variables.

## Expected Python Script Structure

The workflow expects scripts/process_s3_report.py with the following capabilities:

#!/usr/bin/env python3
"""
S3 Report Processor
Processes S3 bucket reports and generates insights
"""

import boto3
import os
import pandas as pd
from datetime import datetime

def main():
# Get environment variables
bucket = os.getenv('S3_REPORT_BUCKET')
path = os.getenv('S3_REPORT_PATH')

    # Initialize S3 client
    s3_client = boto3.client('s3')
    
    # Process reports
    # ... implementation details ...
    
    print("Report processing completed successfully")

if __name__ == "__main__":
main()

## Monitoring and Troubleshooting

### Viewing Execution Logs
1. Go to Actions → Process S3 Report workflow
2. Click on the latest run
3. Expand each step to view detailed logs

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| AWS Authentication Failed | Verify AWS secrets are correctly set in repository settings |
| Missing Python Dependencies | Ensure requirements.txt includes all required packages |
| S3 Bucket Not Accessible | Check IAM permissions and bucket policies |
| Python Script Errors | Check script syntax and environment variables |

### Debug Mode
Add debug output to workflow:

- name: Debug Environment
  run: |
  echo "Bucket: ${{ secrets.S3_REPORT_BUCKET }}"
  echo "Path: ${{ secrets.S3_REPORT_PATH }}"
  echo "Region: ${{ secrets.AWS_DEFAULT_REGION }}"

## Output and Results

The workflow generates:
1. Console Output: Processing status and metrics
2. Processed Reports: Typically stored in designated output location
3. Log Files: Available in GitHub Actions interface

## Security Considerations

### Best Practices
1. Use Least Privilege: Grant only necessary S3 permissions
2. Rotate Credentials: Regularly rotate AWS access keys
3. Audit Logs: Monitor GitHub Actions execution logs
4. Secret Management: Never hardcode credentials in workflow files

### Secret Rotation Procedure
1. Generate new AWS credentials
2. Update GitHub repository secrets
3. Test workflow with new credentials
4. Disable old credentials

## Extending the Workflow

### Adding Email Notifications
- name: Send Email Report
  uses: dawidd6/action-send-mail@v3
  with:
  server_address: smtp.gmail.com
  server_port: 465
  username: ${{ secrets.MAIL_USERNAME }}
  password: ${{ secrets.MAIL_PASSWORD }}
  subject: 'S3 Report Processing Complete'
  to: devops@example.com
  from: GitHub Actions
  body: 'S3 report processing completed successfully.'

### Integrating with Monitoring Systems
- name: Send Metrics to CloudWatch
  run: |
  # Push custom metrics to AWS CloudWatch
  aws cloudwatch put-metric-data \
  --namespace S3Reports \
  --metric-name ProcessedFiles \
  --value $processed_count

## Support and Maintenance

### Regular Maintenance Tasks
- [ ] Update Python dependencies quarterly
- [ ] Review and rotate AWS credentials bi-monthly
- [ ] Audit IAM permissions annually
- [ ] Monitor workflow execution logs weekly

### Getting Help
- Check existing workflow runs for patterns
- Review Python script logs
- Verify AWS CloudTrail logs for S3 access
- Consult GitHub Actions documentation

## Related Resources
- GitHub Actions Documentation: https://docs.github.com/en/actions
- AWS SDK for Python (Boto3) Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- S3 Storage Analytics: https://docs.aws.amazon.com/AmazonS3/latest/userguide/analytics-storage-class.html

---
