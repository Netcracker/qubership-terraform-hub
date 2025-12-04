#!/usr/bin/env python3
import boto3
import os
import time
import requests
import json
import shutil
import tempfile
import urllib3
import re
import base64
from datetime import datetime
import sys
from io import BytesIO

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

def embed_json_files_in_html(s3_client, bucket_name, html_key, report_prefix):
    """
    Embed JSON files directly into index.html to make it self-contained.
    Replaces fetch("*.json") calls with inline JSON data.
    """
    print(f"  Processing HTML file: {html_key}")

    try:
        # Download the HTML file
        response = s3_client.get_object(Bucket=bucket_name, Key=html_key)
        html_content = response['Body'].read().decode('utf-8')

        # Find all JSON file references
        json_patterns = [
            r'fetch\("([^"]+\.json)"\)',  # fetch("data/test-cases.json")
            r"fetch\('([^']+\.json)'\)",  # fetch('data/test-cases.json')
            r'\.load\("([^"]+\.json)"\)',  # .load("data/test-cases.json")
            r"\.load\('([^']+\.json)'\)",  # .load('data/test-cases.json')
            r'src="([^"]+\.json)"',        # src="data/test-cases.json"
            r"src='([^']+\.json)'",        # src='data/test-cases.json'
        ]

        json_files_found = set()
        for pattern in json_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                # Handle relative paths
                if match.startswith('/'):
                    json_key_path = match[1:]  # Remove leading slash
                elif match.startswith('./'):
                    # Get directory from HTML path
                    html_dir = '/'.join(html_key.split('/')[:-1])
                    json_key_path = f"{html_dir}/{match[2:]}"
                else:
                    # Get directory from HTML path
                    html_dir = '/'.join(html_key.split('/')[:-1])
                    json_key_path = f"{html_dir}/{match}"

                json_files_found.add(json_key_path)

        print(f"  Found {len(json_files_found)} JSON file references")

        # Process each JSON file and embed it
        for json_key_path in json_files_found:
            try:
                # Download the JSON file
                json_response = s3_client.get_object(Bucket=bucket_name, Key=json_key_path)
                json_data = json_response['Body'].read().decode('utf-8')

                # Parse to ensure it's valid JSON
                parsed_json = json.loads(json_data)

                # Create replacement
                json_escaped = json.dumps(parsed_json).replace('\\', '\\\\').replace('"', '\\"')

                # Get just the filename for matching
                json_filename = json_key_path.split('/')[-1]
                escaped_filename = re.escape(json_filename)

                # Replace all occurrences of this JSON file with embedded data
                # Pattern for fetch calls with double quotes
                fetch_double_pattern = rf'fetch\("([^"]*{escaped_filename})"\)'
                html_content = re.sub(
                    fetch_double_pattern,
                    f'Promise.resolve({{json: () => Promise.resolve({json_escaped})}})',
                    html_content
                )

                # Pattern for fetch calls with single quotes
                fetch_single_pattern = rf"fetch\('([^']*{escaped_filename})'\)"
                html_content = re.sub(
                    fetch_single_pattern,
                    f'Promise.resolve({{json: () => Promise.resolve({json_escaped})}})',
                    html_content
                )

                print(f"    Embedded: {json_filename}")

            except Exception as e:
                print(f"    ⚠ Could not embed {json_key_path}: {str(e)}")

        # Upload the modified HTML file back to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=html_key,
            Body=html_content.encode('utf-8'),
            ContentType='text/html'
        )

        print(f"  ✓ Updated HTML file with embedded JSON data")
        return True

    except Exception as e:
        print(f"  ✗ Error processing HTML file: {str(e)}")
        return False

def process_allure_report_folder(s3_client, bucket_name, report_prefix):
    """
    Process all index.html files in the allure-report folder to embed JSON data
    """
    print(f"  Looking for index.html files in: {report_prefix}")

    try:
        # List all objects in the allure-report folder
        objects = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=report_prefix
        )

        html_files = []
        if 'Contents' in objects:
            for obj in objects['Contents']:
                if obj['Key'].endswith('index.html'):
                    html_files.append(obj['Key'])

        print(f"  Found {len(html_files)} index.html files")

        for html_file in html_files:
            # Get the directory containing the HTML file
            html_dir = '/'.join(html_file.split('/')[:-1]) + '/'

            # Process the HTML file to embed JSON data
            embed_json_files_in_html(s3_client, bucket_name, html_file, html_dir)

            # Also look for any other HTML files in the same directory
            dir_objects = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=html_dir
            )

            if 'Contents' in dir_objects:
                for obj in dir_objects['Contents']:
                    if obj['Key'].endswith('.html') and obj['Key'] != html_file:
                        print(f"  Also processing: {obj['Key']}")
                        embed_json_files_in_html(s3_client, bucket_name, obj['Key'], html_dir)

        return len(html_files) > 0

    except Exception as e:
        print(f"  ✗ Error processing report folder: {str(e)}")
        return False

def find_allure_results_files(s3_client, source_bucket, folder_path):
    """
    Find all allure-results files in a folder, handling nested structures
    """
    print(f"  Searching for allure-results in: {folder_path}")

    try:
        # First, try the direct path
        source_allure_prefix = f"{folder_path}allure-results/"

        # List objects in source allure-results
        allure_objects = s3_client.list_objects_v2(
            Bucket=source_bucket,
            Prefix=source_allure_prefix
        )

        if 'Contents' in allure_objects and len(allure_objects['Contents']) > 0:
            print(f"  Found {len(allure_objects['Contents'])} files in direct path")
            return allure_objects['Contents'], source_allure_prefix

        # If not found, search for any subfolders that might contain allure-results
        print(f"  No files found in direct path, searching subfolders...")

        # List all contents in the folder
        all_objects = s3_client.list_objects_v2(
            Bucket=source_bucket,
            Prefix=folder_path
        )

        if 'Contents' not in all_objects:
            print(f"  No objects found in folder")
            return [], None

        # Look for allure-results in any path
        allure_files = []
        allure_prefix = None

        for obj in all_objects['Contents']:
            if 'allure-results' in obj['Key'] and not obj['Key'].endswith('/'):
                allure_files.append(obj)
                # Extract the prefix
                key_parts = obj['Key'].split('/')
                for i in range(len(key_parts)):
                    if key_parts[i] == 'allure-results':
                        allure_prefix = '/'.join(key_parts[:i+1]) + '/'
                        break

        if allure_files:
            print(f"  Found {len(allure_files)} allure-results files in subfolders")
            return allure_files, allure_prefix

        print(f"  No allure-results files found")
        return [], None

    except Exception as e:
        print(f"  ✗ Error searching for files: {str(e)}")
        return [], None

def copy_allure_results_to_destination(s3_client, source_bucket, dest_bucket, folder_prefix, folder_name):
    """Copy files from source bucket's allure-results to dest bucket's results folder (flat structure)"""
    # Clean the folder name
    folder_name = folder_name.rstrip('/')

    # Construct folder path
    folder_path = f"{folder_prefix}{folder_name}/"

    # Destination is flat structure: results/
    dest_results_prefix = "results/"

    print(f"  Will copy files to: {dest_results_prefix} (flat structure)")

    try:
        # Find allure-results files (handles nested structure)
        allure_files, source_allure_prefix = find_allure_results_files(s3_client, source_bucket, folder_path)

        if not allure_files:
            print(f"  ⚠ No allure-results files found")
            return 0

        print(f"  Source prefix: {source_allure_prefix}")

        # Copy each file to destination results folder (flat structure)
        files_copied = 0
        for obj in allure_files:
            source_key = obj['Key']

            # Skip if it's a directory marker
            if source_key.endswith('/'):
                continue

            # Get filename only (no path)
            filename = source_key.split('/')[-1]

            # Create unique filename to avoid conflicts between folders
            # Use folder_name as prefix to keep files unique
            unique_filename = f"{folder_name}_{filename}"
            dest_key = f"{dest_results_prefix}{unique_filename}"

            print(f"    Copying: {filename} -> {unique_filename} ({obj.get('Size', 'unknown')} bytes)")
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

            print(f"    Copying: {relative_path}")

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

def cleanup_destination_results(s3_client, dest_bucket, folder_name):
    """Clean up files from destination results folder for this specific folder"""
    # Clean the folder name
    folder_name = folder_name.rstrip('/')

    # We need to clean up only the files that were copied for this folder
    # Files are named with prefix: {folder_name}_filename
    prefix_to_clean = f"results/{folder_name}_"

    print(f"  Cleaning up files with prefix: {prefix_to_clean}")

    try:
        # List objects that match the prefix
        result_objects = s3_client.list_objects_v2(
            Bucket=dest_bucket,
            Prefix=prefix_to_clean
        )

        delete_count = 0
        if 'Contents' in result_objects:
            for obj in result_objects['Contents']:
                s3_client.delete_object(Bucket=dest_bucket, Key=obj['Key'])
                delete_count += 1
                print(f"    Deleted: {obj['Key']}")

        if delete_count > 0:
            print(f"  ✓ Cleaned up {delete_count} files from {prefix_to_clean}")
        else:
            print(f"  ⚠ No files found to clean up with prefix {prefix_to_clean}")

    except Exception as e:
        print(f"  ⚠ Error cleaning up: {str(e)}")

def main():
    # Get environment variables
    source_bucket = os.getenv('SOURCE_BUCKET', 'qstp-consul')
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
    print(f"\nWorkflow:")
    print(f"1. Copy allure-results to {dest_bucket}/results/ (flat structure)")
    print(f"2. Generate report via API")
    print(f"3. Copy latest report from {dest_bucket}/reports/latest/ to {source_bucket}/allure-report/")
    print(f"4. Process HTML files to embed JSON data")

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
                    # 1. Copy files from allure-results to destination bucket's results folder (flat)
                    print(f"\n[Step 1/4] Copying allure-results to destination bucket...")
                    files_copied = copy_allure_results_to_destination(
                        s3_client, source_bucket, dest_bucket, prefix, folder_name
                    )

                    if files_copied == 0:
                        print(f"  ⚠ No files to process, skipping remaining steps")

                        # Still create lock file to mark as processed
                        lock_content = f"""Processed at: {datetime.now().isoformat()}
Folder: {folder_name}
Files processed: 0
Status: No allure-results found
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
                    print(f"\n[Step 2/4] Generating report via API...")

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
                            print(f"\n[Step 3/4] Copying latest report to source bucket...")
                            report_files_copied = copy_latest_report_to_source(
                                s3_client, dest_bucket, source_bucket, prefix, folder_name
                            )

                            if report_files_copied == 0:
                                print(f"  ⚠ No report files found in {dest_bucket}/reports/latest/")
                                print(f"  This might mean report generation failed or hasn't completed yet")
                            else:
                                # 4. Process HTML files to embed JSON data
                                print(f"\n[Step 4/4] Processing HTML files to embed JSON data...")
                                source_report_prefix = f"{prefix}{folder_name}/allure-report/"
                                html_processed = process_allure_report_folder(
                                    s3_client, source_bucket, source_report_prefix
                                )

                                if html_processed:
                                    print(f"  ✓ Successfully processed HTML files")
                                else:
                                    print(f"  ⚠ No HTML files found or processed")

                    # 5. Clean up: Remove temporary results from destination bucket
                    print(f"\n[Cleanup] Cleaning up temporary files from destination bucket...")
                    cleanup_destination_results(s3_client, dest_bucket, folder_name)

                    # 6. Create executed.lck file to mark as processed
                    lock_content = f"""Processed at: {datetime.now().isoformat()}
Folder: {folder_name}
Files processed: {files_copied}
Report files copied: {report_files_copied if 'report_files_copied' in locals() else 0}
HTML files processed: {'Yes' if 'html_processed' in locals() and html_processed else 'No'}
Allure results copied to: {dest_bucket}/results/ (as {folder_name}_* files)
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