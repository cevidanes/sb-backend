#!/usr/bin/env python3
"""
Script to delete ALL files from Cloudflare R2 bucket.

Usage:
    # From inside the Docker container:
    docker exec -it sb-api python delete_all_r2_files.py
    
    # Non-interactive mode (skip confirmations):
    docker exec sb-api python delete_all_r2_files.py --yes
    
    # Or locally with environment variables:
    R2_ENDPOINT=xxx R2_ACCESS_KEY=xxx R2_SECRET_KEY=xxx R2_BUCKET=xxx python delete_all_r2_files.py
"""
import os
import sys
import argparse
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def get_r2_client():
    """Create boto3 S3 client configured for Cloudflare R2."""
    endpoint = os.environ.get('R2_ENDPOINT')
    access_key = os.environ.get('R2_ACCESS_KEY')
    secret_key = os.environ.get('R2_SECRET_KEY')
    region = os.environ.get('R2_REGION', 'auto')
    
    if not all([endpoint, access_key, secret_key]):
        print("ERROR: Missing R2 configuration!")
        print("Required environment variables:")
        print("  - R2_ENDPOINT")
        print("  - R2_ACCESS_KEY")
        print("  - R2_SECRET_KEY")
        print(f"  - R2_BUCKET (optional, defaults to 'brainglass-media')")
        sys.exit(1)
    
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        )
    )


def list_all_objects(client, bucket):
    """List all objects in the bucket using pagination."""
    all_objects = []
    continuation_token = None
    
    print(f"Listing all objects in bucket '{bucket}'...")
    
    while True:
        kwargs = {'Bucket': bucket, 'MaxKeys': 1000}
        if continuation_token:
            kwargs['ContinuationToken'] = continuation_token
        
        try:
            response = client.list_objects_v2(**kwargs)
        except ClientError as e:
            print(f"ERROR listing objects: {e}")
            return []
        
        contents = response.get('Contents', [])
        all_objects.extend(contents)
        
        print(f"  Found {len(contents)} objects (total: {len(all_objects)})")
        
        if not response.get('IsTruncated'):
            break
            
        continuation_token = response.get('NextContinuationToken')
    
    return all_objects


def delete_all_objects(client, bucket, objects):
    """Delete all objects from the bucket."""
    if not objects:
        print("No objects to delete.")
        return
    
    total = len(objects)
    deleted = 0
    failed = 0
    
    print(f"\nDeleting {total} objects...")
    
    # Delete in batches of 1000 (S3 API limit)
    BATCH_SIZE = 1000
    
    for i in range(0, len(objects), BATCH_SIZE):
        batch = objects[i:i + BATCH_SIZE]
        batch_keys = [{'Key': obj['Key']} for obj in batch]
        
        try:
            response = client.delete_objects(
                Bucket=bucket,
                Delete={
                    'Objects': batch_keys,
                    'Quiet': True
                }
            )
            
            errors = response.get('Errors', [])
            batch_deleted = len(batch) - len(errors)
            deleted += batch_deleted
            failed += len(errors)
            
            if errors:
                for error in errors[:3]:
                    print(f"  ERROR: {error.get('Key')}: {error.get('Code')} - {error.get('Message')}")
                if len(errors) > 3:
                    print(f"  ... and {len(errors) - 3} more errors")
            
            print(f"  Deleted batch {i // BATCH_SIZE + 1}: {batch_deleted} objects (total: {deleted}/{total})")
            
        except ClientError as e:
            print(f"  ERROR deleting batch: {e}")
            failed += len(batch)
    
    print(f"\n{'='*50}")
    print(f"SUMMARY:")
    print(f"  Total objects: {total}")
    print(f"  Deleted: {deleted}")
    print(f"  Failed: {failed}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description='Delete all files from Cloudflare R2 bucket')
    parser.add_argument('--yes', '-y', action='store_true', 
                        help='Skip confirmation prompts (non-interactive mode)')
    args = parser.parse_args()
    
    bucket = os.environ.get('R2_BUCKET', 'brainglass-media')
    
    print("=" * 50)
    print("CLOUDFLARE R2 - DELETE ALL FILES")
    print("=" * 50)
    print(f"Bucket: {bucket}")
    print()
    
    if not args.yes:
        # Confirm with user
        print("⚠️  WARNING: This will DELETE ALL files from the bucket!")
        confirm = input("Type 'DELETE ALL' to confirm: ")
        
        if confirm != 'DELETE ALL':
            print("Aborted.")
            sys.exit(0)
        
        print()
    
    # Create client
    client = get_r2_client()
    
    # List all objects
    objects = list_all_objects(client, bucket)
    
    if not objects:
        print("\n✅ Bucket is already empty!")
        return
    
    # Show some sample keys
    print(f"\nSample files to delete:")
    for obj in objects[:5]:
        size_kb = obj.get('Size', 0) / 1024
        print(f"  - {obj['Key']} ({size_kb:.1f} KB)")
    if len(objects) > 5:
        print(f"  ... and {len(objects) - 5} more files")
    
    if not args.yes:
        # Final confirmation
        print()
        confirm2 = input(f"Confirm deletion of {len(objects)} files? (yes/no): ")
        if confirm2.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    # Delete all
    delete_all_objects(client, bucket, objects)
    
    print("\n✅ Done!")


if __name__ == '__main__':
    main()

