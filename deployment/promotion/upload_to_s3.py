import boto3
import os

# Set your AWS credentials (replace with your own values)
# aws_access_key = os.environ['AWS_ACCESS_KEY_ID']
# aws_secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
# aws_region = 'us-east-1'  # Change to your desired region


def get_base_path_to_artifact(artifacts):
    if len(artifacts) == 0:
        # This shouldn't happen often, if ever.
        print("No artifacts found; cannot construct path.")
        return None
    path = artifacts[0]['path']
    split_path = str.split(path, '/')
    path = '/'.join(split_path[1:-1])
    path = path.replace("hmpreprod", "hm", 1)
    return path


def get_key_with_extension(artifact):
    """Return artifact key with extension. Add one if not already present."""
    key = artifact['key']
    if '.' in key:
        return key
    filename_extension = artifact['filename_extension']
    return f"{key}.{filename_extension}"


def update_artifact_path(artifact, base_path):
    artifact['path'] = f"{base_path}"


def upload_to_s3(artifact, s3_url):
    # Connect to s3
    session = boto3.Session()
    s3 = session.client('s3')

    print(f"about to upload artifact {artifact}")

    og_key = artifact['key']
    key_with_extension = get_key_with_extension(artifact)
    path = artifact['path']
    bucket_name = 'vertaai-user-data-dev-us-east-1'
    s3_key = f"testing-hm-preprod/{path}/{key_with_extension}"

    # Upload the file to S3
    s3.upload_file(og_key, bucket_name, s3_key)
    print(f"File '{og_key}' uploaded to '{s3_key}' in bucket '{bucket_name}'.")



