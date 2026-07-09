"""
AWS Lambda: qstp-s3-notification

Project: qstp (ATP — Automated Testing Platform)
Cost tag: cost-usage=qstp (recommended; currently untagged in AWS — costs appear under 'untagged')

Purpose:
    Triggers GitHub Actions when new QSTP test results are uploaded to S3.
    Listens for object events under Result/<test-type>/YYYY-MM-DD/HH-MM-SS/ and
    sends a repository_dispatch event to process-s3-report workflow.

AWS configuration (us-east-1):
    Function:  qstp-s3-notification
    Runtime:   python3.14
    Handler:   lambda_function.lambda_handler
    Memory:    128 MB
    Timeout:   3 sec
    IAM role:  eks-tech-lambda

S3 triggers:
    - qstp-results
    - qstp-consul

Environment variables (set in Lambda, not in git):
    GITHUB_TOKEN       — GitHub PAT for repository_dispatch API
    GITHUB_REPO_OWNER  — e.g. Netcracker
    GITHUB_REPO_NAME   — e.g. qubership-terraform-hub

Related workflow:
    .github/workflows/process-s3-report.yml (event: s3-new-result-directory)

Owner: Denis Arychkov (qstp)
"""

import json
import os
import re
from datetime import datetime
import urllib.request
import urllib.error


def lambda_handler(event, context):
    """
    Process S3 event records and trigger GitHub Actions for new test result directories.

    Expected S3 key pattern:
        Result/<test-type>/YYYY-MM-DD/HH-MM-SS/<file>

    Skips:
        - Keys under Report/ (generated reports, avoids loops)
        - Directories that do not match the timestamp pattern
        - Duplicate directory keys within a single invocation
    """
    print(f"=== S3 Lambda Trigger Started ===")

    try:
        GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
        GITHUB_REPO_OWNER = os.environ['GITHUB_REPO_OWNER']
        GITHUB_REPO_NAME = os.environ['GITHUB_REPO_NAME']

        print(f"Repo: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")

        processed_directories = set()
        results = []

        for record in event.get('Records', []):
            try:
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']

                print(f"📁 Processing: s3://{bucket}/{key}")

                if key.startswith('Report/'):
                    print(f"   ⏭️  Skipping - is a report directory")
                    continue

                if not key.endswith('/'):
                    directory_key = '/'.join(key.split('/')[:-1]) + '/'
                else:
                    directory_key = key

                pattern = r'^Result/[^/]+/\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2}/$'

                if re.match(pattern, directory_key):
                    if directory_key in processed_directories:
                        print(f"   ⏭️  Skipping - already processed")
                        continue

                    processed_directories.add(directory_key)
                    print(f"   ✅ Matched directory: {directory_key}")

                    success, message = trigger_github_action(
                        directory_key,
                        bucket,
                        GITHUB_TOKEN,
                        GITHUB_REPO_OWNER,
                        GITHUB_REPO_NAME
                    )

                    results.append({
                        'directory': directory_key,
                        'success': success,
                        'message': message
                    })

                else:
                    print(f"   ⏭️  Skipping - doesn't match pattern")

            except KeyError as e:
                print(f"   ❌ Malformed S3 record: {str(e)}")
                continue

        print(f"=== Processing Complete ===")
        print(f"Processed {len(results)} directories")

        successful = sum(1 for r in results if r['success'])
        return {
            'statusCode': 200 if successful > 0 else 400,
            'body': json.dumps({
                'processed': len(results),
                'successful': successful,
                'results': results
            })
        }

    except KeyError as e:
        print(f"❌ Missing environment variable: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Missing env var: {str(e)}'})
        }
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def trigger_github_action(directory_key, bucket, token, owner, repo):
    """
    Call GitHub repository_dispatch API to start process-s3-report workflow.

    Dispatches event_type 's3-new-result-directory' with directory metadata
    in client_payload.
    """
    try:
        directory_path = directory_key.rstrip('/')
        path_parts = directory_path.split('/')

        test_type = path_parts[1] if len(path_parts) > 1 else 'unknown'
        timestamp_path = '/'.join(path_parts[2:]) if len(path_parts) > 2 else ''
        date_part = path_parts[2] if len(path_parts) > 2 else ''
        time_part = path_parts[3] if len(path_parts) > 3 else ''

        url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"

        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'AWS-Lambda-S3-Result-Trigger'
        }

        payload = {
            'event_type': 's3-new-result-directory',
            'client_payload': {
                'directory': directory_path,
                'test_type': test_type,
                'timestamp_path': timestamp_path,
                'date': date_part,
                'time': time_part,
                'bucket': bucket,
                'triggered_at': datetime.now().isoformat(),
                'event_source': 'aws-s3-lambda'
            }
        }

        print(f"   📤 Calling GitHub API for test type: {test_type}...")

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status

            if status == 204:
                print(f"   ✅ GitHub Action triggered (204)")
                return True, "GitHub Action triggered successfully"
            else:
                print(f"   ⚠️  Unexpected GitHub response: {status}")
                return False, f"Unexpected status: {status}"

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"   ❌ GitHub HTTP Error {e.code}: {error_body[:200]}")
        return False, f"GitHub error {e.code}"

    except urllib.error.URLError as e:
        print(f"   ❌ Network error: {e.reason}")
        return False, f"Network error: {e.reason}"

    except Exception as e:
        print(f"   ❌ Request failed: {str(e)}")
        return False, f"Request failed: {str(e)}"
