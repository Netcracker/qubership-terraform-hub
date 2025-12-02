#!/usr/bin/env python3
import boto3
import os
import time
import requests
import json
import shutil
import tempfile
from datetime import datetime
import sys

def login_to_allure(allure_url, username, password):
    """Login to Allure API and get token"""
    try:
        url = f"{allure_url}/login"
        headers = {
            'accept': '*/*',
            'Content-Type': 'application/json'
        }
        data = {
            'username': username,
            'password': password
        }

        print(f"  Logging in to Allure API...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()

        # Extract token from response
        # Assuming the token is in the response body or headers
        # You might need to adjust this based on the actual API response
        token = response.json().get('token') or response.headers.get('Authorization')

        if not token:
            print(f"  ✗ No token found in response")
            return None

        print(f"  ✓ Successfully logged in")
        return token

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Login failed: {str(e)}")
        return None
    except json.JSONDecodeError:
        print(f"  ✗ Invalid JSON response from login")
        return None

def generate_report(allure_url, token, project_id):
    """Generate Allure report"""
    try:
        url = f"{allure_url}/generate-report"
        params = {'project_id': project_id}
        headers = {
            'accept': '*/*',
            'Authorization': f'Bearer {token}'
        }

        print(f"  Generating report for project: {project_id}...")
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()

        print(f"  ✓ Report generation triggered successfully")
        return True

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Report generation failed: {str(e)}")
        return False

def download_report(allure_url, token, project_id, output_path):
    """Download generated Allure report"""
    try:
        url = f"{allure_url}/report/export"
        params = {'project_id': project_id}
        headers = {
            'accept': '*/*',
            'Authorization': f'Bearer {token}'
        }

        print(f"  Downloading report...")
        response = requests.get(url, headers=headers, params=params, stream=True, timeout=120)
        response.raise_for_status()

        # Save the report
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  ✓ Report downloaded to {output_path}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Report download failed: {str(e)}")
        return False

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

    # Validate credentials
    if not allure_username or not allure_password:
        print("✗ Error: ALLURE_USERNAME and ALLURE_PASSWORD must be set as environment variables")
        sys.exit(1)

    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=aws_region)

    # List all folders for the target date
    prefix = f"Result/consul/{target_date}/"
    response = s3_client.list_objects_v2(
        Bucket=source_bucket,
        Prefix=prefix,
        Delimiter='/'
    )

    folders_processed = 0
    folders_skipped = 0
    report_files = []

    # Create temporary directory for downloaded reports
    temp_dir = tempfile.mkdtemp(prefix='allure_reports_')
    print(f"Created temp directory: {temp_dir}")

    try:
        # Process each folder
        if 'CommonPrefixes' in response:
            for folder in response['CommonPrefixes']:
                folder_name = folder['Prefix'].replace(prefix, '').rstrip('/')

                print(f"\n{'='*60}")
                print(f"Processing folder: {folder_name}")
                print(f"{'='*60}")

                # 1. Go to folder
                folder_prefix = f"{prefix}{folder_name}/"

                # 2. Check for executed.lck file
                lock_key = f"{folder_prefix}executed.lck"
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

                # 3. Copy files from allure-results to destination bucket root
                source_allure_prefix = f"{folder_prefix}allure-results/"
                temp_files = []

                try:
                    # List objects in allure-results
                    allure_objects = s3_client.list_objects_v2(
                        Bucket=source_bucket,
                        Prefix=source_allure_prefix
                    )

                    if 'Contents' not in allure_objects or len(allure_objects['Contents']) == 0:
                        print(f"⚠ No allure-results found in {folder_name}")
                        files_copied = 0
                    else:
                        # Copy each file to destination bucket root
                        files_copied = 0
                        for obj in allure_objects['Contents']:
                            source_key = obj['Key']
                            filename = source_key.split('/')[-1]
                            dest_key = filename  # Copy to root of destination bucket

                            # Add timestamp to avoid conflicts
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            unique_dest_key = f"{timestamp}_{folder_name}_{filename}"

                            print(f"  Copying: {filename} -> {dest_bucket}/{unique_dest_key}")
                            s3_client.copy_object(
                                CopySource={'Bucket': source_bucket, 'Key': source_key},
                                Bucket=dest_bucket,
                                Key=unique_dest_key
                            )
                            temp_files.append(unique_dest_key)
                            files_copied += 1

                        print(f"✓ Copied {files_copied} files to destination bucket root")

                    # 4. Execute curl commands
                    print(f"  Starting API calls...")

                    # Login to get token
                    token = login_to_allure(allure_url, allure_username, allure_password)
                    if not token:
                        print(f"  ✗ Skipping API calls due to login failure")
                        continue

                    # Generate report
                    if generate_report(allure_url, token, project_id):
                        # Wait 1 minute
                        print(f"  Waiting 60 seconds for report generation...")
                        for i in range(60, 0, -1):
                            print(f"    {i} seconds remaining...", end='\r')
                            time.sleep(1)
                        print(f"    Done waiting!{' '*20}")

                        # Download report
                        report_filename = f"allure_report_{folder_name}_{timestamp}.zip"
                        report_path = os.path.join(temp_dir, report_filename)

                        if download_report(allure_url, token, project_id, report_path):
                            report_files.append(report_path)
                            print(f"  ✓ Report saved: {report_path}")

                    # 5. Delete copied files from destination bucket
                    if temp_files:
                        print(f"  Cleaning up temporary files from {dest_bucket}...")
                        for file_key in temp_files:
                            try:
                                s3_client.delete_object(Bucket=dest_bucket, Key=file_key)
                                print(f"    Deleted: {file_key}")
                            except Exception as e:
                                print(f"    ✗ Failed to delete {file_key}: {str(e)}")

                    # Create executed.lck file to mark as processed
                    lock_content = f"""Processed at: {datetime.now().isoformat()}
Folder: {folder_name}
Files processed: {files_copied}
Report generated: {len(report_files) > 0}
"""
                    s3_client.put_object(
                        Bucket=source_bucket,
                        Key=lock_key,
                        Body=lock_content.encode('utf-8')
                    )
                    print(f"✓ Created executed.lck file")

                    folders_processed += 1

                except Exception as e:
                    print(f"✗ Error processing folder {folder_name}: {str(e)}")
                    import traceback
                    traceback.print_exc()

        # Print summary
        print(f"\n{'='*60}")
        print("PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Total folders found: {len(response.get('CommonPrefixes', []))}")
        print(f"Folders processed: {folders_processed}")
        print(f"Folders skipped (had executed.lck): {folders_skipped}")
        print(f"Reports downloaded: {len(report_files)}")

        # Save report list for GitHub Actions artifact
        if report_files:
            report_list_file = os.path.join(os.path.dirname(temp_dir), 'allure_reports_list.txt')
            with open(report_list_file, 'w') as f:
                for report_path in report_files:
                    f.write(f"{report_path}\n")

            print(f"\nReport files list saved to: {report_list_file}")
            print("These files will be available as GitHub Actions artifacts")

            # Also save to GITHUB_OUTPUT for workflow use
            if 'GITHUB_OUTPUT' in os.environ:
                with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                    f.write(f"reports_count={len(report_files)}\n")
                    f.write(f"reports_dir={temp_dir}\n")

        if folders_processed == 0 and folders_skipped == 0:
            print("⚠ No folders found for the specified date")

    finally:
        # Clean up temporary directory (or keep it for artifacts)
        print(f"\nTemporary directory preserved for artifacts: {temp_dir}")
        # Uncomment to clean up:
        # shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    main()