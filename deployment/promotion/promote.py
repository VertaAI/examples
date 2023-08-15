#!/usr/bin/env python3
"""
This is a Python script that will copy/promote a Verta Build from one environment
to another.

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
- VERTA_SOURCE_WORKSPACE_0: The workspace associated with the build on the source Verta instance
- VERTA_DEST_HOST: The destination Verta instance to promote to
- VERTA_DEST_EMAIL: The email address for authentication to the destination Verta instance
- VERTA_DEST_DEV_KEY: The dev key associated to the email address on the destination Verta instance
- VERTA_DEST_WORKSPACE: The workspace associated with the build on the destination Verta instance
- VERTA_DEST_REGISTERED_MODEL_ID: [optional] The ID of the registered model to promote to. If missing, we'll create a new registered model

Optional environment variables to configure curl usage:
VERTA_CURL_OPTS: Options to pass to curl. Defaults to '-O'

With these values set, run the script. The script will not attempt to delete any data and will fail if the registered
model (if an existing one has not been provided) or version already exists in the destination.
"""

from locale import atoi

import requests
import os
import datetime

from upload_to_s3 import upload_to_s3, get_base_path_to_artifact, update_artifact_path

env_vars = ['VERTA_SOURCE_MODEL_VERSION_ID', 'VERTA_SOURCE_HOST', 'VERTA_SOURCE_EMAIL',
            'VERTA_SOURCE_DEV_KEY',
            'VERTA_SOURCE_WORKSPACE_0', 'VERTA_DEST_HOST', 'VERTA_DEST_EMAIL',
            'VERTA_DEST_DEV_KEY',
            'VERTA_DEST_WORKSPACE']

opt_env_vars = ['VERTA_DEST_REGISTERED_MODEL_ID']

params = {}

proxies = {
    "http": None,
    "https": None
}

if not os.environ.get('VERTA_DEST_WORKSPACE'):
    host = 'https://' + os.environ.get(
        'VERTA_DEST_HOST') + '/api/v1/uac-proxy/workspace/getVisibleWorkspaces'
    headers_dict = {'grpc-metadata-source': 'PythonClient',
                    'grpc-metadata-email': os.environ.get('VERTA_DEST_EMAIL'),
                    'grpc-metadata-developer_key': os.environ.get('VERTA_DEST_DEV_KEY')}
    workspaces_dest = requests.get(host, headers=headers_dict, proxies=proxies)

    source_workspace_id = os.environ.get('VERTA_SOURCE_WORKSPACE_0')
    host = 'https://' + os.environ.get(
        'VERTA_SOURCE_HOST') + '/api/v1/uac-proxy/workspace/getVisibleWorkspaces'
    headers_dict = {'grpc-metadata-source': 'PythonClient',
                    'grpc-metadata-email': os.environ.get('VERTA_SOURCE_EMAIL'),
                    'grpc-metadata-developer_key': os.environ.get('VERTA_SOURCE_DEV_KEY')}
    workspaces_source = requests.get(host, headers=headers_dict, proxies=proxies)

    source_workspace = None
    for item in workspaces_source.json()['workspace']:
        if 'id' in item.keys() and item['id'] == source_workspace_id:
            if 'org_name' in item.keys():
                source_workspace = item['org_name']
            else:
                source_workspace = item['username']

    if source_workspace == None:
        print('Source workspace ID could not be matched')

    for item in workspaces_dest.json()['workspace']:
        if 'org_name' in item.keys() and item['org_name'] == source_workspace:
            os.environ['VERTA_DEST_WORKSPACE'] = item['org_name']
        elif 'username' in item.keys() and item['username'] == source_workspace:
            os.environ['VERTA_DEST_WORKSPACE'] = item['username']
else:
    source_workspace = os.environ.get('VERTA_DEST_WORKSPACE')

for param_name in env_vars:
    param = os.environ.get(param_name)
    if not param:
        raise KeyError("Missing environment variable %s", param_name)
    params[param_name] = param

for param_name in opt_env_vars:
    param = os.environ.get(param_name)
    params[param_name] = param

curl_opts = os.environ.get('VERTA_CURL_OPTS')
if curl_opts:
    params['VERTA_CURL_OPTS'] = curl_opts
else:
    params['VERTA_CURL_OPTS'] = ''
params['VERTA_CURL_OPTS'] += f' -H @curl_headers'

config = {
    'source': {
        'model_version_id': atoi(params['VERTA_SOURCE_MODEL_VERSION_ID']),  # [2:-2]),
        'host': params['VERTA_SOURCE_HOST'],
        'email': params['VERTA_SOURCE_EMAIL'],
        'devkey': params['VERTA_SOURCE_DEV_KEY'],
        'workspace': params['VERTA_SOURCE_WORKSPACE_0'],
        'workspace_name': source_workspace
    },
    'dest': {
        'host': params['VERTA_DEST_HOST'],
        'email': params['VERTA_DEST_EMAIL'],
        'devkey': params['VERTA_DEST_DEV_KEY'],
        'workspace': params['VERTA_DEST_WORKSPACE'],
        'registered_model_id': params['VERTA_DEST_REGISTERED_MODEL_ID']
    }
}


def copy_fields(fields, src, dest):
    for field in fields:
        if field in src.keys():
            dest[field] = src[field]


def auth_context(host, email, devkey, workspace):
    return {'headers': {'Grpc-metadata-scheme': 'https', 'Grpc-metadata-source': 'PythonClient',
                        'Grpc-metadata-email': email, 'Grpc-metadata-developer_key': devkey},
            'host': host,
            'workspace': workspace
            }


def post(auth, path, body):
    auth['headers']['Content-Type'] = 'application/json'
    body['workspaceName'] = auth['workspace']
    try:
        res = requests.post("https://{}{}".format(auth["host"], path), headers=auth['headers'],
                            json=body, proxies=proxies)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        if e.response.text:
            print(f"Error: {e.response.text}")
        raise e
    return res.json()


def get(auth, path):
    try:
        res = requests.get("https://{}{}".format(auth["host"], path), headers=auth['headers'],
                           proxies=proxies)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        if e.response.text:
            print(f"Error: {e.response.text}")
        raise e
    return res.json()


def put(auth, path, body):
    try:
        res = requests.put("https://{}{}".format(auth["host"], path), headers=auth['headers'],
                           json=body, proxies=proxies)
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
        res = requests.patch("https://{}{}".format(auth["host"], path), headers=auth['headers'],
                             json=body, proxies=proxies)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        if e.response.text:
            print(f"Error: {e.response.text}")
        raise e
    return res.json()


def get_build(auth, build_id):
    path = "/api/v1/deployment/builds/{}".format(build_id)
    return get(auth, path)


def get_builds(auth, source):
    path = "/api/v1/deployment/builds/?workspaceName={}&model_version_id={}".format(
        source['workspace_name'], source['model_version_id'])
    print(f"\n\nPATH = {path}\n\n")
    builds = get(auth, path)
    print(f"\n\nBUILDS = {builds}\n\n")
    return get(auth, path)


def get_model_version(auth, model_version_id):
    return get(auth, '/api/v1/registry/model_versions/{}'.format(model_version_id))[
        'model_version']


def get_registered_model(auth, registered_model_id):
    return get(auth, '/api/v1/registry/registered_models/{}'.format(registered_model_id))[
        'registered_model']


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
    if 'REQUESTS_CA_BUNDLE' not in os.environ:
        curl_cmd = "curl -o %s %s '%s'" % (key, params['VERTA_CURL_OPTS'], url)
    else:
        curl_cmd = "curl --cacert %s -o %s %s '%s'" % (
            os.environ['REQUESTS_CA_BUNDLE'], key, params['VERTA_CURL_OPTS'], url)
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
        downloaded_artifacts.append(
            {'key': artifact['key'], 'artifact_type': artifact['artifact_type'], 'path': artifact['path'], 'filename_extension': artifact['filename_extension']})

    model_artifact_request = {
        'method': 'GET',
        'model_version_id': model_version_id
    }
    copy_fields(['artifact_type', 'key'], model_artifact, model_artifact_request)
    download_artifact(auth, model_version_id, model_artifact_request)

    return downloaded_artifacts


def upload_artifact(auth, model_version_id, artifact):
    key = artifact['key']
    print("Uploading artifact '%s' to s3" % key)

    upload_to_s3(artifact, "")

    print("Uploading artifact '%s'" % key)
    print(artifact)
    
    artifact_request = {
        'method': 'PUT',
        'model_version_id': model_version_id,
        'key': key
    }
    put_url = signed_artifact_url(auth, model_version_id, artifact_request)
    data = open(key, 'rb')
    headers_dict = {
        'Grpc-metadata-source': 'PythonClient',
        'Content-type': 'application/octet-stream',
        'Grpc-metadata-email': os.environ['VERTA_DEST_EMAIL'],
        'Grpc-metadata-developer_key': os.environ['VERTA_DEST_DEV_KEY']
    }
    put_response = requests.put(put_url, data=data, headers=headers_dict)

    if not put_response.ok:
        raise Exception("Failed to put artifact (%d %s). Key: %s\tURL: %s\tText: %s" % (
            put_response.status_code,
            put_response.reason, key, put_url, put_response.text))

    check_url = signed_artifact_url(auth, model_version_id,
                                    {'method': 'GET', 'model_version_id': model_version_id,
                                     'key': key})
    check = requests.get(check_url, headers=headers_dict)
    if not check.ok:
        raise Exception("Failed to verify artifact '%s' upload at URL %s" % (key, check_url))

    etag = put_response.headers["ETag"]

    commit_artifact_part(auth, model_version_id, key, etag)
    return put_url


def upload_artifacts(auth, model_version_id, artifacts):
    print("Uploading %d artifacts" % len(artifacts))
    uploaded_artifacts = {}

    # Update paths
    base_path = get_base_path_to_artifact(artifacts)
    for artifact in artifacts:
        update_artifact_path(artifact, base_path)
        print(f"Updated artifact path to {artifact['path']}")

    for artifact in artifacts:
        uploaded_artifacts[artifact["key"]] = upload_artifact(auth, model_version_id, artifact)
    return uploaded_artifacts


def get_promotion_data(_config):
    source = _config['source']
    model_version_id = source['model_version_id']

    print("Fetching promotion data for model version %d" % source['model_version_id'])
    source_auth = auth_context(source['host'], source['email'], source['devkey'],
                               source['workspace'])
    model_version = get_model_version(source_auth, model_version_id)

    all_builds = get_builds(source_auth, source)

    time_format = '%Y-%m-%dT%H:%M:%S.%fZ'

    build = None
    latest_date = None
    for b in all_builds['builds']:
        print(f"\n\nBUILDS = {b}\n\n")
        if 'self_contained' in b['creator_request']:
            build_date = datetime.datetime.strptime(b['date_created'], time_format)
            if not latest_date or build_date > latest_date:
                latest_date = build_date
                build = b

    if not build or not latest_date:
        print(
            "No self contained builds found for model version id %d, promotion stopped." % source[
                'model_version_id'])
        raise SystemExit(1)

    model = get_registered_model(source_auth, model_version['registered_model_id'])
    artifacts = download_artifacts(source_auth, model_version_id, model_version['artifacts'],
                                   model_version['model'])

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
    copy_fields(['labels', 'custom_permission', 'name', 'readme_text', 'resource_visibility',
                 'description'], source_model, model)
    return post(auth, path, model)['registered_model']


def create_model_version(auth, source_model_version, promoted_model):
    print("Creating model version '%s'" % source_model_version['version'])
    path = '/api/v1/registry/registered_models/{}/model_versions'.format(promoted_model['id'])
    model_version = {}
    if 'labels' in source_model_version.keys():
        model_version['labels'] = source_model_version['labels']

    fields = ['artifacts', 'attributes', 'environment', 'version', 'readme_text', 'model',
              'description', 'labels']
    copy_fields(fields, source_model_version, model_version)
    return post(auth, path, model_version)['model_version']


def patch_model(auth, registered_model_id, model_version_id, model):
    print("Updating model artifact for model version '%s'" % model_version_id)

    path = '/api/v1/registry/registered_models/{}/model_versions/{}'.format(registered_model_id,
                                                                            model_version_id)
    update = {'model': model}
    return patch(auth, path, update)


def create_build(auth, model_version_id, external_location, source_build):
    print("Creating build of model version '%s'" % model_version_id)
    cr = source_build['creator_request']
    path = '/api/v1/deployment/workspace/{}/builds'.format(auth['workspace'])
    build = {
        'external_location': external_location,
        'model_version_id': int(model_version_id),
        'requires_root': cr['requires_root'],
        'scan_external': cr['scan_external'],
        'self_contained': cr['self_contained'],
        'uses_flask': cr['uses_flask']
    }
    return post(auth, path, build)


def update_build_message(auth, source_build, dest_build):
    message = source_build['message']
    print("Setting %d byte build message" % len(message))
    put(auth, "/api/v1/deployment/builds/{}/message".format(dest_build['id']), message)


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
    dest = _config['dest']

    dest_auth = auth_context(dest['host'], dest['email'], dest['devkey'], dest['workspace'])

    print("Starting promotion")
    build_location = upload_build(promotion['build'])
    if not dest['registered_model_id']:
        model = create_model(dest_auth, promotion['model'], promotion['artifacts'])
    else:
        model = get_registered_model(dest_auth, dest['registered_model_id'])
        print("Using existing registered model '%s'" % model['name'])
    model_version = create_model_version(dest_auth, promotion['model_version'], model)

    artifacts_and_model = promotion['artifacts']
    artifacts_and_model.append(model_version['model'])
    artifact_paths = upload_artifacts(dest_auth, model_version['id'], artifacts_and_model)

    # Standard RMVs will have artifact path 'model' while ER->RMVs will have artifact path 'model.pkl'
    model_artifact = model_version['model']
    if 'model' in artifact_paths.keys():
        model_artifact['path'] = artifact_paths['model']
    else:
        model_artifact['path'] = artifact_paths['model.pkl']
    patch_model(dest_auth, model['id'], model_version['id'], model_artifact)

    dest_build = create_build(dest_auth, model_version['id'], build_location, promotion['build'])
    update_build_message(dest_auth, promotion['build'], dest_build)
    return dest_build


def promote(_config):
    promotion = get_promotion_data(_config)
    promoted_build = create_promotion(_config, promotion)
    print("Promoted build %d created." % promoted_build['id'])


promote(config)
