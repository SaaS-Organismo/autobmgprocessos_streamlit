import os
import tempfile
import zipfile
from datetime import datetime
import boto3
from decouple import config
from concurrent.futures import ThreadPoolExecutor, as_completed

import time

AWS_S3_BUCKET_NAME = config("AWS_S3_BUCKET_NAME")


def download_file(s3_client, bucket_name, file_key, download_dir):
    """
    Downloads a single file from S3 to the specified directory.
    """
    temp_file_path = os.path.join(download_dir, os.path.basename(file_key))
    s3_client.download_file(bucket_name, file_key, temp_file_path)
    return temp_file_path



def zip_s3_bucket_contents(case_id):
    #time.sleep(3)
    #return "", None
    """
    Zips all files in an S3 bucket folder documents/downloads/{case_id} and returns a pre-signed URL for download
    """
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
            region_name=config("AWS_REGION"),
        )

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_filename = f'case_{case_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            zip_path = os.path.join(temp_dir, zip_filename)

            # List all objects in the bucket with the specific prefix
            objects = s3_client.list_objects_v2(
                Bucket=AWS_S3_BUCKET_NAME,
                Prefix=f"documents/downloads/{case_id}/",
            )

            if "Contents" not in objects:
                return None, f"No files found for case ID {case_id}"

            # Filter files (ignore directories)
            file_keys = [
                obj["Key"] for obj in objects["Contents"] if not obj["Key"].endswith("/")
            ]
            total_files = len(file_keys)

            if total_files == 0:
                return None, f"No valid files found for case ID {case_id}"

            # Multi-threaded file download
            downloaded_files = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(download_file, s3_client, AWS_S3_BUCKET_NAME, file_key, temp_dir)
                    for file_key in file_keys
                ]

                for future in as_completed(futures):
                    try:
                        downloaded_files.append(future.result())
                    except Exception as e:
                        print(f"Error downloading file: {e}")

            # Create a ZIP file with downloaded files
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in downloaded_files:
                    zipf.write(file_path, os.path.basename(file_path))
                    os.remove(file_path)  # Clean up temporary file

            # Upload the ZIP file to S3
            zip_key = f"documents/downloads/zips/{case_id}/{zip_filename}"
            s3_client.upload_file(zip_path, AWS_S3_BUCKET_NAME, zip_key)

            # Generate pre-signed URL (valid for 1 hour)
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": AWS_S3_BUCKET_NAME, "Key": zip_key},
                ExpiresIn=3600,
            )

            # Create a lifecycle rule for the zip file to be deleted after 1 hour
            lifecycle_config = {
                "Rules": [
                    {
                        "ID": f"DeleteZipAfter1Hour_{zip_filename}",
                        "Filter": {"Prefix": f"documents/downloads/zips/{case_id}/"},
                        "Status": "Enabled",
                        "Expiration": {"Days": 1},
                    }
                ]
            }

            try:
                s3_client.put_bucket_lifecycle_configuration(
                    Bucket=AWS_S3_BUCKET_NAME, LifecycleConfiguration=lifecycle_config
                )
            except Exception as e:
                return None, str(e)

            return presigned_url, None

    except Exception as e:
        print(e)
        return None, str(e)

