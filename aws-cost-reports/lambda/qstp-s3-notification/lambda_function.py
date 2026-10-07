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
    GITHUB_TOKEN       — GitHub PAT for repository_dispatch API stored in Secrats Manager's secret repository_dispatch_event_token
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
import boto3
from functools import lru_cache

@lru_cache(maxsize=1)
def get_github_token():
    secret = boto3.client('secretsmanager').get_secret_value(SecretId='repository_dispatch_event_token')
    return json.loads(secret['SecretString'])['GITHUB_REPOSITORY_DISPATCH_TOKEN']

def lambda_handler(event, context):
    """
    Trigger GitHub Actions when new test results are uploaded to S3 under Result/ folder.
    """
    print(f"=== S3 Lambda Trigger Started ===")
    
    try:
        # Get environment variables
        GITHUB_TOKEN = get_github_token()
        GITHUB_REPO_OWNER = os.environ['GITHUB_REPO_OWNER']
        GITHUB_REPO_NAME = os.environ['GITHUB_REPO_NAME']
        
        print(f"Repo: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
        
        # Track processed directories to avoid duplicates
        processed_directories = set()
        results = []
        
        # Process all S3 events
        for record in event.get('Records', []):
            try:
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                
                print(f"📁 Processing: s3://{bucket}/{key}")
                
                # Skip if it's a report directory (to avoid infinite loops)
                if key.startswith('Report/'):
                    print(f"   ⏭️  Skipping - is a report directory")
                    continue
                
                # Extract directory from key
                # If it's a file like: Result/[anything]/YYYY-MM-DD/HH-MM-SS/file.xml
                # We want the directory: Result/[anything]/YYYY-MM-DD/HH-MM-SS/
                if not key.endswith('/'):
                    # It's a file, extract the directory
                    directory_key = '/'.join(key.split('/')[:-1]) + '/'
                else:
                    directory_key = key
                
                # Match pattern: Result/*/YYYY-MM-DD/HH-MM-SS/
                # This will match any folder structure under Result/ that has date/time format
                pattern = r'^Result/[^/]+/\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2}/$'
                
                if re.match(pattern, directory_key):
                    # Avoid processing same directory multiple times
                    if directory_key in processed_directories:
                        print(f"   ⏭️  Skipping - already processed")
                        continue
                    
                    processed_directories.add(directory_key)
                    print(f"   ✅ Matched directory: {directory_key}")
                    
                    # Trigger GitHub Action
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
        
        # Return summary
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
    Trigger GitHub Action via repository_dispatch API
    """
    try:
        # Clean directory path
        directory_path = directory_key.rstrip('/')
        
        # Extract timestamp path and test type
        # directory_path format: Result/[test-type]/YYYY-MM-DD/HH-MM-SS
        path_parts = directory_path.split('/')
        
        # Extract test type (the part after Result/)
        test_type = path_parts[1] if len(path_parts) > 1 else 'unknown'
        
        # Extract timestamp path (everything after Result/[test-type]/)
        timestamp_path = '/'.join(path_parts[2:]) if len(path_parts) > 2 else ''
        date_part = path_parts[2] if len(path_parts) > 2 else ''
        time_part = path_parts[3] if len(path_parts) > 3 else ''
        
        # Prepare GitHub API request
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
        
        # Make HTTP request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            response_body = response.read().decode('utf-8')
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
