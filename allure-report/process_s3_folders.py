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
            print(f"  Response headers: {dict(response.headers)}")

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

    def download_report(self, project_id, output_path):
        """Download generated Allure report"""
        try:
            url = f"{self.base_url}/report/export"
            params = {'project_id': project_id}

            print(f"  Downloading report...")
            print(f"  URL: {url}")

            response = self.session.get(url, params=params, stream=True, timeout=120)

            print(f"  Response status: {response.status_code}")
            print(f"  Response headers: {dict(response.headers)}")

            response.raise_for_status()

            # Check if response is actually a file
            content_type = response.headers.get('Content-Type', '')
            content_length = response.headers.get('Content-Length', 'unknown')

            print(f"  Content-Type: {content_type}")
            print(f"  Content-Length: {content_length}")

            # Save the report
            with open(output_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if content_length != 'unknown' and int(content_length) > 0:
                            percent = (downloaded / int(content_length)) * 100
                            print(f"  Download progress: {downloaded}/{content_length} bytes ({percent:.1f}%)", end='\r')

            print(f"\n  ✓ Report downloaded successfully")
            file_size = os.path.getsize(output_path)
            print(f"  Saved to: {output_path} ({file_size} bytes)")
            return True

        except requests.exceptions.RequestException as e:
            print(f"  ✗ Report download failed: {str(e)}")
            if hasattr(e, 'response') and e.response:
                print(f"  Response status: {e.response.status_code}")
                print(f"  Response headers: {dict(e.response.headers)}")
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
    print(f"Note: SSL verification is DISABLED for self-signed certificates")

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
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                files_copied = 0

                try:
                    # List objects in allure-results
                    allure_objects = s3_client.list_objects_v2(
                        Bucket=source_bucket,
                        Prefix=source_allure_prefix
                    )

                    if 'Contents' not in allure_objects or len(allure_objects['Contents']) == 0:
                        print(f"⚠ No allure-results found in {folder_name}")
                    else:
                        # Copy each file to destination bucket root
                        files_copied = 0
                        for obj in allure_objects['Contents']:
                            source_key = obj['Key']
                            # Skip if it's a directory marker
                            if source_key.endswith('/'):
                                continue

                            filename = source_key.split('/')[-1]

                            # Create unique filename with timestamp
                            unique_dest_key = f"temp_{timestamp}_{folder_name}_{filename}"

                            print(f"  Copying: {filename} -> {dest_bucket}/{unique_dest_key}")
                            s3_client.copy_object(
                                CopySource={'Bucket': source_bucket, 'Key': source_key},
                                Bucket=dest_bucket,
                                Key=unique_dest_key
                            )
                            temp_files.append(unique_dest_key)
                            files_copied += 1

                        print(f"✓ Copied {files_copied} files to destination bucket root")

                    # 4. Execute API calls if files were copied
                    if files_copied > 0:
                        print(f"  Starting API calls...")

                        # Initialize Allure API client
                        allure_client = AllureAPIClient(allure_url, allure_username, allure_password)

                        # Login to get token
                        if not allure_client.login():
                            print(f"  ✗ Skipping API calls due to login failure")
                        else:
                            # Generate report
                            if allure_client.generate_report(project_id):
                                # Wait 1 minute
                                print(f"  Waiting 60 seconds for report generation...")
                                for i in range(60, 0, -1):
                                    print(f"    {i:2d} seconds remaining...", end='\r')
                                    time.sleep(1)
                                print(f"    Done waiting!{' '*20}")

                                # Download report
                                report_filename = f"allure_report_{folder_name}_{timestamp}.zip"
                                report_path = os.path.join(temp_dir, report_filename)

                                if allure_client.download_report(project_id, report_path):
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
Report generated: {'Yes' if files_copied > 0 and len(report_files) > 0 else 'No'}
Timestamp: {timestamp}
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
        total_folders = len(response.get('CommonPrefixes', []))
        print(f"Total folders found: {total_folders}")
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

            # Copy the list file to workspace for artifact upload
            workspace_list_file = os.path.join(os.getcwd(), 'allure_reports_list.txt')
            shutil.copy2(report_list_file, workspace_list_file)
            print(f"Copied to workspace: {workspace_list_file}")

        if folders_processed == 0 and folders_skipped == 0 and total_folders == 0:
            print("⚠ No folders found for the specified date")

    finally:
        # Keep temp directory for artifact upload
        print(f"\nTemporary directory with reports: {temp_dir}")
        if os.path.exists(temp_dir) and os.listdir(temp_dir):
            print("Files in temp directory:")
            for f in os.listdir(temp_dir):
                filepath = os.path.join(temp_dir, f)
                size = os.path.getsize(filepath)
                print(f"  - {f} ({size} bytes)")

if __name__ == '__main__':
    main()