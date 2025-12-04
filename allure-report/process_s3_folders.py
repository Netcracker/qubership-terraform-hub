#!/usr/bin/env python3
import boto3
import os
import time
import requests
import json
import shutil
import tempfile
import urllib3
from datetime import datetime
import sys

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class AllureAPIClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = False  # Disable SSL verification
        self.token = None
        self.csrf_token = None

    def login(self):
        """Login to Allure API and get token"""
        try:
            url = f"{self.base_url}/login"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json'
            }
            data = {
                'username': self.username,
                'password': self.password
            }

            print(f"  Logging in to Allure API...")
            print(f"  URL: {url}")

            response = self.session.post(url, headers=headers, json=data, timeout=30)

            print(f"  Response status: {response.status_code}")
            response.raise_for_status()

            # Parse JSON response
            response_data = response.json()
            print(f"  ✓ Login successful: {response_data.get('meta_data', {}).get('message', 'No message')}")

            # Extract access_token from data.access_token
            self.token = response_data.get('data', {}).get('access_token')

            if not self.token:
                print(f"  ✗ No access_token found in response")
                return False

            # Extract CSRF token from cookies
            cookies = response.cookies
            self.csrf_token = cookies.get('csrf_access_token')

            print(f"  ✓ Token obtained, length: {len(self.token)}")
            print(f"  Token preview: {self.token[:50]}...")
            print(f"  Token expires in: {response_data['data'].get('expires_in', 'unknown')} seconds")
            if self.csrf_token:
                print(f"  CSRF token: {self.csrf_token[:20]}...")

            # Update session headers with token
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}',
                'X-CSRF-TOKEN': self.csrf_token if self.csrf_token else ''
            })

            return True

        except json.JSONDecodeError as e:
            print(f"  ✗ Invalid JSON response: {str(e)}")
            print(f"  Response text: {response.text[:200]}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Login request failed: {str(e)}")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error during login: {str(e)}")
            return False

    def generate_report(self, project_id):
        """Generate Allure report"""
        try:
            url = f"{self.base_url}/generate-report"
            params = {'project_id': project_id}

            print(f"  Generating report for project: {project_id}...")
            print(f"  URL: {url}")

            response = self.session.get(url, params=params, timeout=60)

            print(f"  Response status: {response.status_code}")

            response.raise_for_status()

            print(f"  ✓ Report generation triggered successfully")

            # Try to parse response
            try:
                response_data = response.json()
                print(f"  Response JSON: {response_data}")
            except:
                print(f"  Response text: {response.text[:200]}")

            return True

        except requests.exceptions.RequestException as e:
            print(f"  ✗ Report generation failed: {str(e)}")
            if hasattr(e, 'response') and e.response:
                print(f"  Response status: {e.response.status_code}")
                print(f"  Response text: {e.response.text[:200]}")
            return False

def copy_allure_results_to_destination(s3_client, source_bucket, dest_bucket, folder_prefix, folder_name):
    """Copy files from source bucket's allure-results to dest bucket's results folder"""
    # Handle nested folder structure: folder_name might already include subfolders
    # For example: folder_name could be "00-20-18/00-20-18"

    # Clean the folder name - remove trailing slash if present
    folder_name = folder_name.rstrip('/')

    # Construct source path - check for both with and without trailing slash
    source_paths_to_try = [
        f"{folder_prefix}{folder_name}/allure-results/",
        f"{folder_prefix}{folder_name}/allure-results"  # Without trailing slash
    ]

    dest_results_prefix = f"results/{folder_name}/"

    print(f"  Looking for allure-results in folder: {folder_name}")

    for source_allure_prefix in source_paths_to_try:
        print(f"  Trying source path: {source_allure_prefix}")

        try:
            # List objects in source allure-results
            allure_objects = s3_client.list_objects_v2(
                Bucket=source_bucket,
                Prefix=source_allure_prefix,
                MaxKeys=1  # Just check if there are any objects
            )

            if 'Contents' in allure_objects and len(allure_objects['Contents']) > 0:
                print(f"  ✓ Found files in: {source_allure_prefix}")
                break
            else:
                print(f"  ✗ No files found in: {source_allure_prefix}")
                source_allure_prefix = None
        except Exception as e:
            print(f"  ⚠ Error checking {source_allure_prefix}: {str(e)}")
            source_allure_prefix = None

    if not source_allure_prefix:
        # Try one more approach: list all objects and find allure-results
        print(f"  Searching for allure-results in folder hierarchy...")
        try:
            # List objects in the parent folder
            parent_objects = s3_client.list_objects_v2(
                Bucket=source_bucket,
                Prefix=folder_prefix,
                Delimiter=''
            )

            if 'Contents' in parent_objects:
                for obj in parent_objects['Contents']:
                    if 'allure-results' in obj['Key']:
                        # Extract the allure-results prefix
                        key_parts = obj['Key'].split('/')
                        for i, part in enumerate(key_parts):
                            if part == 'allure-results':
                                source_allure_prefix = '/'.join(key_parts[:i+1]) + '/'
                                print(f"  Found allure-results at: {source_allure_prefix}")
                                break
                        if source_allure_prefix:
                            break

        except Exception as e:
            print(f"  ⚠ Error searching for allure-results: {str(e)}")

    if not source_allure_prefix:
        print(f"  ✗ Could not find allure-results folder")
        return 0

    print(f"  Copying from: {source_allure_prefix}")
    print(f"  Copying to: {dest_results_prefix}")

    try:
        # Now list all objects in the found allure-results
        allure_objects = s3_client.list_objects_v2(
            Bucket=source_bucket,
            Prefix=source_allure_prefix
        )

        files_copied = 0
        if 'Contents' not in allure_objects or len(allure_objects['Contents']) == 0:
            print(f"  ⚠ No files found in {source_allure_prefix}")
            return 0

        print(f"  Found {len(allure_objects['Contents'])} objects in allure-results")

        # Copy each file to destination results folder
        for obj in allure_objects['Contents']:
            source_key = obj['Key']
            # Skip if it's a directory marker
            if source_key.endswith('/'):
                continue

            filename = source_key.split('/')[-1]
            dest_key = f"{dest_results_prefix}{filename}"

            print(f"    Copying: {filename} ({obj.get('Size', 'unknown')} bytes)")
            s3_client.copy_object(
                CopySource={'Bucket': source_bucket, 'Key': source_key},
                Bucket=dest_bucket,
                Key=dest_key
            )
            files_copied += 1

        print(f"  ✓ Copied {files_copied} files to {dest_results_prefix}")
        return files_copied

    except Exception as e:
        print(f"  ✗ Error copying files: {str(e)}")
        return 0

def copy_latest_report_to_source(s3_client, dest_bucket, source_bucket, folder_prefix, folder_name):
    """Copy latest report from dest bucket to source bucket's allure-report folder"""
    # Clean the folder name
    folder_name = folder_name.rstrip('/')

    source_report_prefix = f"{folder_prefix}{folder_name}/allure-report/"
    dest_latest_prefix = f"reports/latest/"

    print(f"  Copying latest report from: {dest_latest_prefix}")
    print(f"  Copying to: {source_report_prefix}")

    try:
        # List all objects in the latest reports folder
        latest_objects = s3_client.list_objects_v2(
            Bucket=dest_bucket,
            Prefix=dest_latest_prefix
        )

        files_copied = 0
        if 'Contents' not in latest_objects or len(latest_objects['Contents']) == 0:
            print(f"  ⚠ No files found in {dest_latest_prefix}")
            return 0

        print(f"  Found {len(latest_objects['Contents'])} objects in latest report")

        # Copy each file to source allure-report folder
        for obj in latest_objects['Contents']:
            source_key = obj['Key']
            # Skip if it's a directory marker
            if source_key.endswith('/'):
                continue

            # Get relative path within latest folder
            relative_path = source_key[len(dest_latest_prefix):]
            if not relative_path:  # Skip if it's the folder itself
                continue

            dest_key = f"{source_report_prefix}{relative_path}"

            # Create parent directories if needed (S3 handles this implicitly, but we log it)
            print(f"    Copying: {relative_path} -> {relative_path}")

            s3_client.copy_object(
                CopySource={'Bucket': dest_bucket, 'Key': source_key},
                Bucket=source_bucket,
                Key=dest_key
            )
            files_copied += 1

        print(f"  ✓ Copied {files_copied} files to {source_report_prefix}")
        return files_copied

    except Exception as e:
        print(f"  ✗ Error copying latest report: {str(e)}")
        return 0

def main():
    # Get environment variables
    source_bucket = os.getenv('SOURCE_BUCKET', 'consul-test')
    dest_bucket = os.getenv('DEST_BUCKET', 'qstp-consul-allure')
    target_date = os.getenv('TARGET_DATE', datetime.now().strftime('%Y-%m-%d'))
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    allure_url = os.getenv('ALLURE_URL', 'https://k8s-qstpallu-allurein-413be1b9d5-1630657851.us-east-1.elb.amazonaws.com/allure-api/allure-docker-service')
    project_id = os.getenv('PROJECT_ID', 'consul-test')

    # Get credentials from environment variables (set as GitHub secrets)
    allure_username = os.getenv('ALLURE_USERNAME')
    allure_password = os.getenv('ALLURE_PASSWORD')

    print(f"Processing date: {target_date}")
    print(f"Source bucket: {source_bucket}")
    print(f"Destination bucket: {dest_bucket}")
    print(f"Allure URL: {allure_url}")
    print(f"Project ID: {project_id}")
    print(f"Note: SSL verification is DISABLED for self-signed certificates")
    print(f"\nNew workflow:")
    print(f"1. Copy allure-results to {dest_bucket}/results/")
    print(f"2. Generate report via API")
    print(f"3. Copy latest report from {dest_bucket}/reports/latest/ to {source_bucket}/allure-report/")

    # Validate credentials
    if not allure_username or not allure_password:
        print("✗ Error: ALLURE_USERNAME and ALLURE_PASSWORD must be set as environment variables")
        sys.exit(1)

    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=aws_region)

    # List all folders for the target date
    prefix = f"Result/consul/{target_date}/"

    try:
        response = s3_client.list_objects_v2(
            Bucket=source_bucket,
            Prefix=prefix,
            Delimiter='/'
        )
    except Exception as e:
        print(f"✗ Error listing objects in bucket: {str(e)}")
        sys.exit(1)

    folders_processed = 0
    folders_skipped = 0

    try:
        # Process each folder
        if 'CommonPrefixes' in response:
            for folder in response['CommonPrefixes']:
                # Get the full folder path relative to the prefix
                folder_path = folder['Prefix']
                # Remove the main prefix to get the folder name
                folder_name = folder_path.replace(prefix, '').rstrip('/')

                print(f"\n{'='*60}")
                print(f"Processing folder: {folder_name}")
                print(f"Full path: {folder_path}")
                print(f"{'='*60}")

                # Check for executed.lck file
                lock_key = f"{folder_path}executed.lck"
                try:
                    s3_client.head_object(Bucket=source_bucket, Key=lock_key)
                    print(f"✓ executed.lck file found - ignoring folder")
                    folders_skipped += 1
                    continue  # Skip to next folder
                except s3_client.exceptions.ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code != '404':
                        print(f"✗ Error checking lock file: {error_code} - {str(e)}")
                        continue

                print(f"✗ No executed.lck file found - starting processing")

                # If no lock file found, process this folder
                try:
                    # 1. Copy files from allure-results to destination bucket's results folder
                    print(f"\nStep 1: Copying allure-results to destination bucket...")
                    files_copied = copy_allure_results_to_destination(
                        s3_client, source_bucket, dest_bucket, prefix, folder_name
                    )

                    if files_copied == 0:
                        print(f"  ⚠ No files to process, skipping API calls")
                        # Debug: List what's actually in the folder
                        print(f"\n  Debug: Listing contents of {folder_path}")
                        try:
                            debug_objects = s3_client.list_objects_v2(
                                Bucket=source_bucket,
                                Prefix=folder_path,
                                Delimiter=''
                            )
                            if 'Contents' in debug_objects:
                                print(f"  Found {len(debug_objects['Contents'])} objects:")
                                for obj in debug_objects['Contents'][:10]:  # Show first 10
                                    print(f"    - {obj['Key']} ({obj.get('Size', 'unknown')} bytes)")
                            if 'CommonPrefixes' in debug_objects:
                                print(f"  Found {len(debug_objects['CommonPrefixes'])} subfolders:")
                                for sub in debug_objects['CommonPrefixes']:
                                    print(f"    - {sub['Prefix']}")
                        except Exception as debug_e:
                            print(f"  Debug error: {str(debug_e)}")

                        # Still create lock file to mark as processed (even with no files)
                        lock_content = f"""Processed at: {datetime.now().isoformat()}
Folder: {folder_name}
Files processed: 0
Status: No allure-results found after search
"""
                        s3_client.put_object(
                            Bucket=source_bucket,
                            Key=lock_key,
                            Body=lock_content.encode('utf-8')
                        )
                        print(f"✓ Created executed.lck file (no files to process)")
                        folders_processed += 1
                        continue

                    # 2. Execute API call to generate report
                    print(f"\nStep 2: Generating report via API...")

                    # Initialize Allure API client
                    allure_client = AllureAPIClient(allure_url, allure_username, allure_password)

                    # Login to get token
                    if not allure_client.login():
                        print(f"  ✗ Skipping report generation due to login failure")
                    else:
                        # Generate report
                        if allure_client.generate_report(project_id):
                            # Wait 1 minute for report generation
                            print(f"\n  Waiting 60 seconds for report generation...")
                            for i in range(60, 0, -1):
                                print(f"    {i:2d} seconds remaining...", end='\r')
                                time.sleep(1)
                            print(f"    Done waiting!{' '*20}")

                            # 3. Copy latest report from destination bucket to source bucket
                            print(f"\nStep 3: Copying latest report to source bucket...")
                            report_files_copied = copy_latest_report_to_source(
                                s3_client, dest_bucket, source_bucket, prefix, folder_name
                            )

                            if report_files_copied == 0:
                                print(f"  ⚠ No report files found in {dest_bucket}/reports/latest/")

                    # 4. Clean up: Remove temporary results from destination bucket
                    print(f"\nStep 4: Cleaning up temporary files from destination bucket...")
                    try:
                        # Delete the temporary results folder
                        results_prefix = f"results/{folder_name}/"

                        # List and delete all objects in the results folder
                        result_objects = s3_client.list_objects_v2(
                            Bucket=dest_bucket,
                            Prefix=results_prefix
                        )

                        if 'Contents' in result_objects:
                            delete_count = 0
                            for obj in result_objects['Contents']:
                                s3_client.delete_object(Bucket=dest_bucket, Key=obj['Key'])
                                delete_count += 1
                            print(f"  ✓ Cleaned up {results_prefix} ({delete_count} files)")
                        else:
                            print(f"  ⚠ No files found to clean up in {results_prefix}")
                    except Exception as e:
                        print(f"  ⚠ Error cleaning up: {str(e)}")

                    # 5. Create executed.lck file to mark as processed
                    lock_content = f"""Processed at: {datetime.now().isoformat()}
Folder: {folder_name}
Files processed: {files_copied}
Report generated: {'Yes' if files_copied > 0 else 'No'}
Allure results copied to: {dest_bucket}/results/{folder_name}/
Allure report copied to: {source_bucket}/{prefix}{folder_name}/allure-report/
"""
                    s3_client.put_object(
                        Bucket=source_bucket,
                        Key=lock_key,
                        Body=lock_content.encode('utf-8')
                    )
                    print(f"\n✓ Created executed.lck file")

                    folders_processed += 1

                except Exception as e:
                    print(f"✗ Error processing folder {folder_name}: {str(e)}")
                    import traceback
                    traceback.print_exc()

        # Print summary
        print(f"\n{'='*60}")
        print("PROCESSING SUMMARY")
        print(f"{'='*60}")
        total_folders = len(response.get('CommonPrefixes', []))
        print(f"Total folders found: {total_folders}")
        print(f"Folders processed: {folders_processed}")
        print(f"Folders skipped (had executed.lck): {folders_skipped}")

        if folders_processed == 0 and folders_skipped == 0 and total_folders == 0:
            print("⚠ No folders found for the specified date")

    except Exception as e:
        print(f"\n✗ Error in main processing loop: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()