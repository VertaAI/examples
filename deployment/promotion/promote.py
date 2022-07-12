#!/usr/bin/env python3
"""
This is a Python script that will copy/promote a Verta Build from one environment
to another.

Configuration is done via environment variables. All are mandatory:

- VERTA_SOURCE_BUILD_ID: The ID of the build to promote
- VERTA_SOURCE_HOST: The source Verta instance to promote from
- VERTA_SOURCE_EMAIL: The email address for authentication to the source Verta instance
- VERTA_SOURCE_DEV_KEY: The dev key associated to the email address on the source Verta instance
- VERTA_SOURCE_WORKSPACE: The workspace associated with the build on the source Verta instance
- VERTA_DEST_HOST: The destination Verta instance to promote to
- VERTA_DEST_EMAIL: The email address for authentication to the destination Verta instance
- VERTA_DEST_DEV_KEY: The dev key associated to the email address on the destination Verta instance
- VERTA_DEST_WORKSPACE: The workspace associated with the build on the destination Verta instance

Optional environment variables to configure curl usage:
VERTA_CURL_OPTS: Options to pass to curl. Defaults to '-O'

With these values set, run the script. The script will not attempt to delete any data and will fail if the model and version already exist in the destination.
"""

from locale import atoi

import requests
import os

env_vars = ['VERTA_SOURCE_BUILD_ID', 'VERTA_SOURCE_HOST', 'VERTA_SOURCE_EMAIL', 'VERTA_SOURCE_DEV_KEY',
            'VERTA_SOURCE_WORKSPACE', 'VERTA_DEST_HOST', 'VERTA_DEST_EMAIL', 'VERTA_DEST_DEV_KEY',
            'VERTA_DEST_WORKSPACE']
params = {}

for param_name in env_vars:
    param = os.environ.get(param_name)
    if not param:
        raise Exception("Missing environment variable %s", param_name)
    params[param_name] = param

curl_opts = os.environ.get('VERTA_CURL_OPTS')
if curl_opts:
    params['VERTA_CURL_OPTS'] = curl_opts
else:
    params['VERTA_CURL_OPTS'] = ''

config = {
    'source': {
        'build_id': atoi(params['VERTA_SOURCE_BUILD_ID']),
        'host': params['VERTA_SOURCE_HOST'],
        'email': params['VERTA_SOURCE_EMAIL'],
        'devkey': params['VERTA_SOURCE_DEV_KEY'],
        'workspace': params['VERTA_SOURCE_WORKSPACE']
    },
    'dest': {
        'host': params['VERTA_DEST_HOST'],
        'email': params['VERTA_DEST_EMAIL'],
        'devkey': params['VERTA_DEST_DEV_KEY'],
        'workspace': params['VERTA_DEST_WORKSPACE']
    }
}


def copy_fields(fields, src, dest):
    for field in fields:
        # Don't try to copy if nothing's there
        if field in src.keys():
            dest[field] = src[field]


def auth_context(host, email, devkey, workspace):
    return {'headers': {'Grpc-metadata-scheme': 'https', 'Grpc-metadata-source': 'PythonClient',
                        'Grpc-metadata-email': email, 'Grpc-metadata-developer_key': devkey}, 'host': host,
            'workspace': workspace
            }


def post(auth, path, body):
    auth['headers']['Content-Type'] = 'application/json'
    body['workspaceName'] = auth['workspace']
    try:
        res = requests.post("https://{}{}".format(auth["host"], path), headers=auth['headers'], json=body)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        if e.response.text:
            print(f"Error: {e.response.text}")
        raise e
    return res.json()


def get(auth, path):
    try:
        res = requests.get("https://{}{}".format(auth["host"], path), headers=auth['headers'])
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        if e.response.text:
            print(f"Error: {e.response.text}")
        raise e
    return res.json()


def put(auth, path, body):
    try:
        res = requests.put("https://{}{}".format(auth["host"], path), headers=auth['headers'], json=body)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        if e.response.text:
            print(f"Error: {e.response.text}")
        raise e
    if len(res.text) > 0:
        return res.json()
    return {}


def patch(auth, path, body):
    try:
        res = requests.patch("https://{}{}".format(auth["host"], path), headers=auth['headers'], json=body)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        if e.response.text:
            print(f"Error: {e.response.text}")
        raise e
    return res.json()


def get_build(auth, build_id):
    path = "/api/v1/deployment/builds/{}".format(build_id)
    return get(auth, path)


def get_model_version(auth, model_version_id):
    return get(auth, '/api/v1/registry/model_versions/{}'.format(model_version_id))['model_version']


def get_registered_model(auth, registered_model_id):
    return get(auth, '/api/v1/registry/registered_models/{}'.format(registered_model_id))['registered_model']


def signed_artifact_url(auth, model_version_id, artifact):
    print("Getting URL for artifact: '%s'" % artifact['key'])
    path = '/api/v1/registry/model_versions/{}/getUrlForArtifact'.format(model_version_id)
    return post(auth, path, artifact)['url']


def commit_artifact_part(auth, model_version_id, artifact_key, etag):
    print("Committing part for artifact: '%s'" % artifact_key)

    path = '/api/v1/registry/model_versions/{}/commitArtifactPart'.format(model_version_id)
    commit = {
        "artifact_part": {
            "etag": etag,
            "part_number": 1
        },
        "key": artifact_key,
        "model_version_id": model_version_id
    }
    return post(auth, path, commit)


def download_artifact(auth, model_version_id, artifact):
    key = artifact['key']
    url = signed_artifact_url(auth, model_version_id, artifact)
    print("Downloading artifact '%s'" % key)
    curl_cmd = "curl %s -o %s '%s'" % (params['VERTA_CURL_OPTS'], key, url)
    os.system(curl_cmd)


def download_artifacts(auth, model_version_id, artifacts, model_artifact):
    print("Downloading %d artifacts" % len(artifacts))

    downloaded_artifacts = []
    for artifact in artifacts:
        artifact_request = {
            'method': 'GET',
            'model_version_id': model_version_id
        }
        copy_fields(['artifact_type', 'key'], artifact, artifact_request)
        download_artifact(auth, model_version_id, artifact_request)
        downloaded_artifacts.append({'key': artifact['key'], 'artifact_type': artifact['artifact_type']})

    model_artifact_request = {
        'method': 'GET',
        'model_version_id': model_version_id
    }
    copy_fields(['artifact_type', 'key'], model_artifact, model_artifact_request)
    download_artifact(auth, model_version_id, model_artifact_request)

    return downloaded_artifacts


def upload_artifact(auth, model_version_id, artifact):
    key = artifact['key']
    print("Uploading artifact '%s'" % key)

    artifact_request = {
        'method': 'PUT',
        'model_version_id': model_version_id,
        'key': key
    }
    put_url = signed_artifact_url(auth, model_version_id, artifact_request)
    data = open(key, 'rb')
    put_response = requests.put(put_url, data=data, headers={'Content-type': 'application/octet-stream'})

    if not put_response.ok:
        raise Exception("Failed to put artifact (%d %s). Key: %s\tURL: %s\tText: %s" % (put_response.status_code,
                        put_response.reason, key, put_url, put_response.text))

    check_url = signed_artifact_url(auth, model_version_id, {'method': 'GET', 'model_version_id': model_version_id,
                                                          'key': key})
    check = requests.get(check_url)
    if not check.ok:
        raise Exception("Failed to verify artifact '%s' upload at URL %s" % (key, check_url))

    etag = put_response.headers["ETag"]

    commit_artifact_part(auth, model_version_id, key, etag)
    return put_url


def upload_artifacts(auth, model_version_id, artifacts):
    print("Uploading %d artifacts" % len(artifacts))
    uploaded_artifacts = {}

    for artifact in artifacts:
        uploaded_artifacts[artifact["key"]] = upload_artifact(auth, model_version_id, artifact)
    return uploaded_artifacts


def get_promotion_data(_config):
    source = _config['source']
    
    print("Fetching promotion data for build %d" % source['build_id'])
    source_auth = auth_context(source['host'], source['email'], source['devkey'], source['workspace'])
    build = get_build(source_auth, _config['source']['build_id'])
    if 'self_contained' not in build['creator_request']:
        print("WARNING: Build %d is not self contained. Endpoint containers will download artifacts at runtime."
              % build['id']
              )

    model_version_id = build['creator_request']['model_version_id']
    model_version = get_model_version(source_auth, model_version_id)
    registered_model_id = model_version['registered_model_id']
    model = get_registered_model(source_auth, registered_model_id)
    artifacts = download_artifacts(source_auth, model_version_id, model_version['artifacts'], model_version['model'])

    promotion = {
        'build': build,
        'model_version': model_version,
        'model': model,
        'artifacts': artifacts
    }

    return promotion


def create_model(auth, source_model, source_artifacts):
    print("Creating registered model '%s'" % source_model['name'])
    path = '/api/v1/registry/workspaces/{}/registered_models'.format(auth['workspace'])
    model = {
        'artifacts': source_artifacts
    }
    copy_fields(['labels', 'custom_permission', 'name', 'readme_text', 'resource_visibility'], source_model, model)
    return post(auth, path, model)['registered_model']


def create_model_version(auth, source_model_version, promoted_model):
    print("Creating model version '%s'" % source_model_version['version'])
    path = '/api/v1/registry/registered_models/{}/model_versions'.format(promoted_model['id'])
    model_version = {}
    if 'labels' in source_model_version.keys():
        model_version['labels'] = source_model_version['labels']

    fields = ['artifacts', 'attributes', 'environment', 'version', 'readme_text', 'model']
    copy_fields(fields, source_model_version, model_version)
    return post(auth, path, model_version)['model_version']


def patch_model(auth, registered_model_id, model_version_id, model):
    print("Updating model artifact for model version '%s'" % model_version_id)

    path = '/api/v1/registry/registered_models/{}/model_versions/{}'.format(registered_model_id, model_version_id)
    update = {'model': model}
    return patch(auth, path, update)


def create_build(auth, model_version_id, external_location):
    print("Creating build of model version '%s'" % model_version_id)
    path = '/api/v1/deployment/workspace/{}/builds'.format(auth['workspace'])
    build = {
        'external_location': external_location,
        'model_version_id': int(model_version_id),
    }
    return post(auth, path, build)


# Modify this function to download and re-upload the build image as needed
def upload_build(source_build):
    source_location = source_build['location']

    # Modify as appropriate
    dest_location = source_location
    print("Uploading from %s to %s" % (source_location, dest_location))
    # This placeholder function simply returns the unmodified source location.
    # Re-uploading the build image is only necessary if the source and destination environments use different S3 buckets
    return dest_location


def create_promotion(_config, promotion):
    source = _config['source']
    dest = _config['dest']
    
    dest_auth = auth_context(dest['host'], dest['email'], dest['devkey'], dest['workspace'])

    print("Starting promotion")
    build_location = upload_build(promotion['build'])
    model = create_model(dest_auth, promotion['model'], promotion['artifacts'])
    model_version = create_model_version(dest_auth, promotion['model_version'], model)

    artifacts_and_model = promotion['artifacts']
    artifacts_and_model.append(model_version['model'])
    artifact_paths = upload_artifacts(dest_auth, model_version['id'], artifacts_and_model)

    model_artifact = model_version['model']
    model_artifact['path'] = artifact_paths['model']
    patch_model(dest_auth, model['id'], model_version['id'], model_artifact)

    return create_build(dest_auth, model_version['id'], build_location)


def promote(_config):
    promotion = get_promotion_data(_config)
    promoted_build = create_promotion(_config, promotion)
    print("Promoted build %d created." % promoted_build['id'])


promote(config)
