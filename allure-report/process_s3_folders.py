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

    folders_to_process = []

    # Check each folder for executed.lck
    if 'CommonPrefixes' in response:
        for folder in response['CommonPrefixes']:
            folder_name = folder['Prefix'].replace(prefix, '').rstrip('/')

            # Check if executed.lck exists
            lock_key = f"{prefix}{folder_name}/executed.lck"
            try:
                s3_client.head_object(Bucket=source_bucket, Key=lock_key)
                print(f"Skipping {folder_name} - executed.lck exists")
                continue
            except s3_client.exceptions.ClientError:
                # Lock file doesn't exist, process this folder
                folders_to_process.append(folder_name)

    if not folders_to_process:
        print("No folders to process")
        return

    print(f"Processing {len(folders_to_process)} folders:")

    for folder_name in folders_to_process:
        print(f"\nProcessing {folder_name}...")

        # Copy allure-results if they exist
        source_allure_prefix = f"{prefix}{folder_name}/allure-results/"

        try:
            # List objects in allure-results
            allure_objects = s3_client.list_objects_v2(
                Bucket=source_bucket,
                Prefix=source_allure_prefix
            )

            if 'Contents' not in allure_objects or len(allure_objects['Contents']) == 0:
                print(f"No allure-results found in {folder_name}")
                continue

            # Copy each file
            for obj in allure_objects['Contents']:
                source_key = obj['Key']
                dest_key = source_key.replace(source_allure_prefix, f"{target_date}/{folder_name}/")

                print(f"Copying: {source_key} -> {dest_key}")
                s3_client.copy_object(
                    CopySource={'Bucket': source_bucket, 'Key': source_key},
                    Bucket=dest_bucket,
                    Key=dest_key
                )

            # Create executed.lck file
            lock_content = f"Processed at {datetime.now().isoformat()}"
            s3_client.put_object(
                Bucket=source_bucket,
                Key=f"{prefix}{folder_name}/executed.lck",
                Body=lock_content.encode('utf-8')
            )

            print(f"Successfully processed {folder_name}")

        except Exception as e:
            print(f"Error processing {folder_name}: {str(e)}")

    # TODO: Add API call here when ready
    print("\nAPI call placeholder - will be implemented later")
    # import requests
    # requests.post('https://api.example.com/webhook', json={
    #     'date': target_date,
    #     'folders': folders_to_process
    # })

if __name__ == '__main__':
    main()