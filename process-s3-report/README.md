ReadingReading
📋 README: S3 Test Results Processing Workflow
🔍 Overview

The Process Consul Test Results workflow is a GitHub Actions pipeline that automatically processes Allure test results stored in AWS S3, generates comprehensive test reports, and distributes them to various destinations. This workflow is triggered either manually or automatically when new test results are available.
⚙️ Workflow Configuration
📌 Basic Information

    File: .github/workflows/process-s3-report.yml

    Workflow Name: Process Consul Test Results

    Primary Trigger: Manual dispatch or repository dispatch events

    Environment: Ubuntu latest runner with 30-minute timeout

🎯 Triggers
1. Manual Trigger (workflow_dispatch)
   yaml

on:
workflow_dispatch:
inputs:
s3_directory:
description: 'S3 Directory Path (e.g., Result/consul/2025-12-10/00-42-50/)'
required: true
default: 'Result/consul/2025-12-10/00-42-50'
type: string

2. Automated Trigger (repository_dispatch)
   yaml

on:
repository_dispatch:
types: [s3-new-consul-directory]

🔧 Environment Variables
yaml

env:
S3_BUCKET: qstp-consul
OUTPUT_DIR: ./allure-report
SINGLE_FILE_DIR: ./allure-single-file
SOURCE_DIR: ./allure-results

🏗️ Job Structure
📊 Main Job: generate-allure-report
Step 1: Repository Checkout

    Checks out the repository code

    Uses actions/checkout@v4

Step 2: AWS Credentials Configuration

    Configures AWS credentials for S3 access

    Uses aws-actions/configure-aws-credentials@v4

    Required Secrets:

        AWS_ACCESS_KEY_ID

        AWS_SECRET_ACCESS_KEY

        AWS_REGION (optional, defaults to us-east-1)

Step 3: S3 Path Parsing

    Parses the S3 directory path from input

    Creates safe identifiers for file naming

    Handles both manual and automated triggers

Step 4: Download Allure Results from S3

    Downloads test result files (.xml, .json, .txt) from specified S3 path

    Synchronizes files to local directory

    Counts and validates downloaded files

Step 5: Install Java and Allure

    Installs Java 17 runtime

    Downloads and installs Allure CLI version 2.35.1

    Sets up system PATH for Allure

Step 6: Generate Allure Reports

    Generates two types of Allure reports:

        Multi-file report: Standard Allure report with multiple files

        Single-file report: Self-contained HTML report

    Validates report generation success

Step 7: Upload Reports to S3

    Uploads generated reports back to S3

    Stores in Report/consul/[timestamp]/ structure

    Provides direct S3 links for access

Step 8: Output Results

    Displays comprehensive summary of processing

    Shows download links and statistics

    Provides troubleshooting guidance

Step 9: Send Email Notification

    Sends email notifications with report links

    Uses SMTP (Gmail) for delivery

    Required Secrets:

        SMTP_USERNAME

        SMTP_PASSWORD

        EMAIL_RECIPIENT_1, EMAIL_RECIPIENT_2, EMAIL_RECIPIENT_ATP

Step 10: Trigger Git Sync

    Triggers additional workflow (allure-sync-results.yaml)

    Ensures results are synchronized to Git repository

🔐 Required Secrets
Secret Name	Description	Example
AWS_ACCESS_KEY_ID	AWS access key for S3 operations	AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY	AWS secret key for S3 operations	wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION	AWS region (optional)	us-east-1
SMTP_USERNAME	SMTP email username	reports@example.com
SMTP_PASSWORD	SMTP email password/app password	yourpassword
EMAIL_RECIPIENT_1	Primary email recipient	team1@example.com
EMAIL_RECIPIENT_2	Secondary email recipient	team2@example.com
EMAIL_RECIPIENT_ATP	Additional recipient	manager@example.com
🚀 Usage Instructions
Manual Execution

    Navigate to Actions tab in GitHub repository

    Select "Process Consul Test Results" workflow

    Click "Run workflow"

    Provide S3 directory path:
    text

Result/consul/YYYY-MM-DD/HH-MM-SS/

    Click "Run workflow"

Automated Execution

    Trigger via repository_dispatch event with payload:
    json

{
"directory": "Result/consul/2025-12-10/00-42-50"
}

📁 File Structure
Input Structure (S3)
text

s3://qstp-consul/
└── Result/
└── consul/
└── YYYY-MM-DD/
└── HH-MM-SS/
├── *.xml
├── *.json
└── *.txt

Output Structure (S3)
text

s3://qstp-consul/
└── Report/
└── consul/
└── YYYY-MM-DD/
└── HH-MM-SS/
├── allure-report/       # Multi-file report
│   ├── index.html
│   ├── data/
│   └── plugins/
├── allure-report-*.html # Single-file report
└── upload-test.txt      # Verification file

🌐 Accessing Reports
Direct URLs

    Multi-file report: https://k8s-nginxs3v-nginxs3g-52e35e9339-1035610716.us-east-1.elb.amazonaws.com/Report/consul/[timestamp]/allure-report/index.html

    Single-file report: https://k8s-nginxs3v-nginxs3g-52e35e9339-1035610716.us-east-1.elb.amazonaws.com/Report/consul/[timestamp]/allure-report-[safe_id].html

S3 Access
text

s3://qstp-consul/Report/consul/[timestamp]/

🛠️ Troubleshooting
Common Issues

    No test files found

        Verify S3 path is correct

        Check files exist in specified directory

        Ensure files have .xml or .json extensions

    Report generation failure

        Check XML file structure conforms to Allure format

        Verify Java and Allure installation succeeded

        Review debug output in workflow logs

    Upload failures

        Verify AWS credentials have write permissions to S3 bucket

        Check network connectivity to S3

        Validate bucket name and region configuration

Debugging Steps

    Check "Download Allure results from S3" step for file counts

    Review "Generate Allure Reports" step for generation logs

    Examine "Output Results" step for final summary

🔄 Integration Points
Downstream Workflows

    allure-sync-results.yaml: Automatically triggered to sync reports to Git

External Dependencies

    AWS S3: Source and destination for test results and reports

    SMTP Server: Email notification delivery (Gmail configured)

    Allure Framework: Test report generation

📧 Notification Template

Email notifications include:

    Success/failure status

    Direct download links for reports

    S3 access information

    Timestamp and source details

⚠️ Important Notes

    Timeout: Job has 30-minute timeout limit

    File Types: Processes .xml, .json, and .txt files only

    Bucket Access: Requires read/write permissions to qstp-consul bucket

    Email Configuration: Uses Gmail SMTP; consider using app passwords for security

    Path Consistency: Input paths should follow Result/consul/YYYY-MM-DD/HH-MM-SS/ pattern

🆘 Support

For issues with this workflow:

    Check workflow execution logs in GitHub Actions

    Verify all required secrets are properly configured

    Ensure S3 bucket and file structure match expected patterns

    Contact DevOps team for configuration assistance

*Last Updated: 2026-01-23*
Maintainer: DevOps Team