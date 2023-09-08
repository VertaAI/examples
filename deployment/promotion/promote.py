#!/usr/bin/env python3
"""
This is a Python script that will copy/promote a Verta Build from one environment
to another.

This script requires client version at least 0.24.1.

- The script will use the model version passed in the VERTA_SOURCE_MODEL_VERSION_ID environment variable
as the model version to promote.
- The latest self-contained build of the model version will be promoted. The promotion process will terminate if no
self-contained builds of the model version are found.
- If you need to create a self-contained build of a model version, use the create_scb.py script.

Configuration is done via environment variables. All are mandatory except VERTA_DEST_REGISTERED_MODEL_ID:

- VERTA_SOURCE_MODEL_VERSION_ID: The ID of the model version to promote
- VERTA_SOURCE_HOST: The source Verta instance to promote from
- VERTA_SOURCE_EMAIL: The email address for authentication to the source Verta instance
- VERTA_SOURCE_DEV_KEY: The dev key associated to the email address on the source Verta instance
- VERTA_SOURCE_WORKSPACE: The workspace associated with the build on the source Verta instance
- VERTA_SOURCE_ORGANIZATION: [optional] The organization associated with the build on the source Verta instance
- VERTA_SOURCE_S3_BUCKET: The S3 bucket where the artifacts are stored
- VERTA_DEST_HOST: The destination Verta instance to promote to
- VERTA_DEST_EMAIL: The email address for authentication to the destination Verta instance
- VERTA_DEST_DEV_KEY: The dev key associated to the email address on the destination Verta instance
- VERTA_DEST_WORKSPACE: The workspace associated with the build on the destination Verta instance
- VERTA_DEST_ORGANIZATION: [optional] The organization associated with the build on the destination Verta instance
- VERTA_DEST_S3_BUCKET: The S3 bucket where the artifacts will be stored
- VERTA_DEST_REGISTERED_MODEL_ID: [optional] The ID of the registered model to promote to. If missing, we'll create a new registered model

With these values set, run the script. The script will not attempt to delete any data and will fail if the registered
model (if an existing one has not been provided) or version already exists in the destination.
"""

from locale import atoi
from dataclasses import dataclass, field
from typing import Optional

import requests
import os
import datetime

from verta import Client

@dataclass
class Config:
    host: str
    email: str
    devkey: str
    organization: Optional[str] = field(default=None)
    workspace: Optional[str] = field(default=None)

source_config = Config(
    host=os.environ.get('VERTA_SOURCE_HOST'),
    email=os.environ.get('VERTA_SOURCE_EMAIL'),
    devkey=os.environ.get('VERTA_SOURCE_DEV_KEY'),
    organization=os.environ.get('VERTA_SOURCE_ORGANIZATION'),
    workspace=os.environ.get('VERTA_SOURCE_WORKSPACE')
)

dest_config = Config(
    host=os.environ.get('VERTA_DEST_HOST'),
    email=os.environ.get('VERTA_DEST_EMAIL'),
    devkey=os.environ.get('VERTA_DEST_DEV_KEY'),
    organization=os.environ.get('VERTA_DEST_ORGANIZATION'),
    workspace=os.environ.get('VERTA_DEST_WORKSPACE')
)

def client_from_config(config):
    client = Client(
        host=config.host,
        email=config.email,
        dev_key=config.devkey,
        organization_name=config.organization,
    )

    if config.workspace:
        client.set_workspace(config.workspace)

    return client

print("Connecting to source Verta instance")
source_client = client_from_config(source_config)
print("Connecting to destination Verta instance")
dest_client = client_from_config(dest_config)

source_model_version_id = os.environ.get('VERTA_SOURCE_MODEL_VERSION_ID')
if not source_model_version_id:
    raise KeyError("Missing environment variable VERTA_SOURCE_MODEL_VERSION_ID")
dest_model_id = os.environ.get('VERTA_DEST_REGISTERED_MODEL_ID')

print("Fetching model version %s" % source_model_version_id)
source_model_version = source_client.get_registered_model_version(source_model_version_id)
source_model = source_client.get_registered_model(id=source_model_version.registered_model_id)
source_builds = source_model_version.list_builds()
if len(source_builds) == 0:
    raise ValueError("No builds found for model version %s" % source_model_version_id)
source_build = source_builds[0]

if dest_model_id:
    print("Fetching destination registered model %s" % dest_model_id)
    dest_model = dest_client.get_registered_model(id=dest_model_id)
else:
    print("Fetching or creating destination registered model %s" % source_model.name)
    dest_model = dest_client.get_or_create_registered_model(name=source_model.name)

# Copy information from the source model to the destination model
print("Copying info from source model to destination model")
dest_model.add_labels([v for v in source_model.get_labels()])

# Create the basic model version
print("Copying info from source model version to destination model version")
dest_model_version = dest_model.create_version(
    name=source_model_version.name,
    labels=[v for v in source_model_version.get_labels()],
    attrs={k: v for k, v in source_model_version.get_attributes().items()},
)

for key in source_model_version.get_artifact_keys():
    artifact = source_model_version.get_artifact(key)
    dest_model_version.log_artifact(key, artifact, overwrite=True)

model = source_model_version.get_model()
dest_model_version.log_model(model, custom_modules=[], overwrite=True)

env = source_model_version.get_environment()
dest_model_version.log_environment(env, overwrite=True)

print("Copying build information")
dest_build = dest_model_version.create_external_build(
    location=source_build.location,
    requires_root=source_build.requires_root,
    scan_external=source_build.scan_external,
    self_contained=source_build.self_contained,
)
dest_build.message = source_build.message

if not source_build.self_contained:
    print("Got non self contained build. Copying artifacts in S3")
    source_bucket = os.environ.get('VERTA_SOURCE_S3_BUCKET')
    if not source_bucket:
        raise KeyError("Missing environment variable VERTA_SOURCE_S3_BUCKET")
    dest_bucket = os.environ.get('VERTA_DEST_S3_BUCKET')
    if not dest_bucket:
        raise KeyError("Missing environment variable VERTA_DEST_S3_BUCKET")

    import boto3

    keys = source_model_version.get_artifact_keys()
    keys.append(source_model_version._MODEL_KEY)

    for key in keys:
        path = source_model_version._get_artifact_msg(key).path
        print(f"Copying {key} via location {path}")

        s3 = boto3.client('s3')

        # Download the file from the source bucket
        s3.download_file(source_bucket, path, 'artifact.tmp')

        # Upload the downloaded file to the destination bucket
        s3.upload_file('artifact.tmp', dest_bucket, path)
