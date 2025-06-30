import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

DO_SPACES_REGION = os.getenv('DO_SPACES_REGION')
DO_SPACES_BUCKET_NAME = os.getenv('DO_SPACES_BUCKET_NAME')
DO_SPACES_ACCESS_KEY = os.getenv('DO_SPACES_ACCESS_KEY')
DO_SPACES_SECRET_KEY = os.getenv('DO_SPACES_SECRET_KEY')


if not all([DO_SPACES_REGION, DO_SPACES_BUCKET_NAME, DO_SPACES_ACCESS_KEY, DO_SPACES_SECRET_KEY]):
    raise ValueError("Missing required DigitalOcean Spaces environment variables")

try:
    s3_client = boto3.client(
        's3',
        region_name=DO_SPACES_REGION,
        endpoint_url=f"https://{DO_SPACES_REGION}.digitaloceanspaces.com",
        aws_access_key_id=DO_SPACES_ACCESS_KEY,
        aws_secret_access_key=DO_SPACES_SECRET_KEY
    )
except Exception as e:
    print(f"Error initializing S3 client: {e}")
    raise


BUCKET_NAME = os.getenv('DO_SPACES_BUCKET_NAME')


def create_resigned_upload_url(user_id: int, file_name: str) -> dict:
    """
    Generates a presigned URL to allow a client to UPLOAD a file.
    """
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    object_name = f"users/{user_id}/originals/{timestamp}_{file_name}"

    try:
        response = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': DO_SPACES_BUCKET_NAME, 'Key': object_name, 'ACL': 'public-read'},
            ExpiresIn=3600
        )
        return {"upload_url": response, "object_name": object_name}
    except ClientError as e:
        print(f"Error generating presigned upload URL: {e}")
        return None



def download_file_from_space(object_name: str, download_path: str):
    """Downloads a file from our Space to a local path for processing."""
    try:
        s3_client.download_file(DO_SPACES_BUCKET_NAME, object_name, download_path)
    except ClientError as e:
        print(f"Error downloading file: {e}")
        raise


def upload_processed_file_to_space(local_path: str, object_name: str) -> dict:
    """
    Uploads a processed file back to our Space and returns its
    permanent, public CDN URL.
    """
    try:
        s3_client.upload_file(
            local_path,
            DO_SPACES_BUCKET_NAME,
            object_name,
            ExtraArgs={'ACL': 'public-read'}
        )

        public_url = f"https://{DO_SPACES_BUCKET_NAME}.{DO_SPACES_REGION}.cdn.digitaloceanspaces.com/{object_name}"

        return {"public_url": public_url, "spaces_uri": object_name}
    except ClientError as e:
        print(f"Error uploading processed file: {e}")
        raise

def delete_file_from_space(object_name: str):
    """
    Deletes a file from the DigitalOcean Space.
    Args:
        object_name (str): The name (key) of the file to delete.
    """
    try:
        print(f"Attempting to delete {object_name} from Space...")
        s3_client.delete_object(Bucket=DO_SPACES_BUCKET_NAME, Key=object_name)
        print(f"Successfully deleted {object_name} from Space.")
        return True
    except ClientError as e:
        print(f"Error deleting file {object_name} from Space: {e}")
        # Depending on your needs, you might want to raise the exception
        # or just return False. For a cleanup task, logging and returning False is often enough.
        return False