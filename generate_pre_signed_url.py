import json
import os
import tempfile
import webbrowser
import zipfile
from datetime import datetime
import boto3
from decouple import config

import time

AWS_S3_BUCKET_NAME = config("AWS_S3_BUCKET_NAME")


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
            zip_filename = (
                f'case_{case_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            )
            zip_path = os.path.join(temp_dir, zip_filename)

            # List all objects in the bucket with the specific prefix
            objects = s3_client.list_objects_v2(
                Bucket=AWS_S3_BUCKET_NAME,
                Prefix=f"documents/downloads/{case_id}/",
            )

            if "Contents" not in objects:
                return None, f"No files found for case ID {case_id}"

            total_files = len(objects["Contents"])

            # Download and zip all files
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for idx, obj in enumerate(objects.get("Contents", []), 1):
                    file_key = obj["Key"]
                    if not file_key.endswith("/"):
                        # Download file to temporary location
                        temp_file_path = os.path.join(
                            temp_dir, os.path.basename(file_key)
                        )
                        s3_client.download_file(AWS_S3_BUCKET_NAME, file_key, temp_file_path)

                        # Add to zip file
                        zipf.write(temp_file_path, os.path.basename(file_key))

                        # Remove temporary file
                        os.remove(temp_file_path)


            # Upload zip file to S3 in a separate zip folder
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

