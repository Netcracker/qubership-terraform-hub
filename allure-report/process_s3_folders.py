#!/usr/bin/env python3
import boto3
import os
from datetime import datetime
import sys

def main():
    # Get environment variables
    source_bucket = os.getenv('SOURCE_BUCKET', 'consul-test')
    dest_bucket = os.getenv('DEST_BUCKET', 'qstp-consul-allure')
    target_date = os.getenv('TARGET_DATE', datetime.now().strftime('%Y-%m-%d'))
    aws_region = os.getenv('AWS_REGION', 'us-east-1')

    print(f"Processing date: {target_date}")
    print(f"Source bucket: {source_bucket}")
    print(f"Destination bucket: {dest_bucket}")

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

    # Process each folder
    if 'CommonPrefixes' in response:
        for folder in response['CommonPrefixes']:
            folder_name = folder['Prefix'].replace(prefix, '').rstrip('/')

            print(f"\n{'='*50}")
            print(f"Processing folder: {folder_name}")
            print(f"{'='*50}")

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
                # Check if error is 404 (not found) vs other error
                error_code = e.response['Error']['Code']
                if error_code != '404':
                    print(f"✗ Error checking lock file: {error_code} - {str(e)}")
                    continue

            print(f"✗ No executed.lck file found")

            # If no lock file found, process this folder

            # 3. Copy allure-results if they exist
            source_allure_prefix = f"{folder_prefix}allure-results/"

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
                    # Copy each file
                    files_copied = 0
                    for obj in allure_objects['Contents']:
                        source_key = obj['Key']
                        dest_key = source_key.replace(source_allure_prefix, f"{target_date}/{folder_name}/")

                        print(f"  Copying: {obj['Key'].split('/')[-1]} -> {dest_bucket}")
                        s3_client.copy_object(
                            CopySource={'Bucket': source_bucket, 'Key': source_key},
                            Bucket=dest_bucket,
                            Key=dest_key
                        )
                        files_copied += 1

                    print(f"✓ Copied {files_copied} files from allure-results")

                # Create executed.lck file to mark as processed
                lock_content = f"Processed at {datetime.now().isoformat()}\nFiles copied: {files_copied}"
                s3_client.put_object(
                    Bucket=source_bucket,
                    Key=lock_key,
                    Body=lock_content.encode('utf-8')
                )
                print(f"✓ Created executed.lck file")

                # 4. Placeholder for curl/API call
                print(f"📡 API call placeholder for {folder_name}")
                # TODO: Implement curl/API call here
                # Example:
                # import requests
                # response = requests.post('https://api.example.com/webhook', json={
                #     'date': target_date,
                #     'folder': folder_name,
                #     'files_copied': files_copied
                # })

                folders_processed += 1

            except Exception as e:
                print(f"✗ Error processing folder {folder_name}: {str(e)}")

    # Print summary
    print(f"\n{'='*50}")
    print("PROCESSING SUMMARY")
    print(f"{'='*50}")
    print(f"Total folders found: {len(response.get('CommonPrefixes', []))}")
    print(f"Folders processed: {folders_processed}")
    print(f"Folders skipped (had executed.lck): {folders_skipped}")

    if folders_processed == 0 and folders_skipped == 0:
        print("⚠ No folders found for the specified date")

if __name__ == '__main__':
    main()