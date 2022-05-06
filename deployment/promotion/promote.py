#!/usr/bin/env python3
"""
This is a Python script that will copy/promote a Verta Endpoint from one environment
to another.

Configuration is done via environment variables. All are mandatory:

- VERTA_ENDPOINT_PATH: The endpoint path, ex. '/test'
- VERTA_SOURCE_HOST: The source Verta instance to promote from
- VERTA_SOURCE_EMAIL: The email address for authentication to the source Verta instance
- VERTA_SOURCE_DEV_KEY: The dev key associated to the email address on the source Verta instance
- VERTA_SOURCE_WORKSPACE: The workspace associated with the endpoint on the source Verta instance
- VERTA_DEST_HOST: The destination Verta instance to promote to
- VERTA_DEST_EMAIL: The email address for authentication to the destination Verta instance
- VERTA_DEST_DEV_KEY: The dev key associated to the email address on the destination Verta instance
- VERTA_DEST_WORKSPACE: The workspace associated with the endpoint on the destination Verta instance

Optional environment variables to configure curl usage:
VERTA_CURL_OPTS: Options to pass to curl. Defaults to '-O'

With these values set, run the script. The script will not attempt to delete any data and will fail if the endpoint already exists in the destination.
"""

import json
import requests
import os

env_vars = ['VERTA_ENDPOINT_PATH', 'VERTA_SOURCE_HOST', 'VERTA_SOURCE_EMAIL', 'VERTA_SOURCE_DEV_KEY',
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
    'endpoint_path': params['VERTA_ENDPOINT_PATH'],
    'source': {
        'host': params['VERTA_SOURCE_HOST'],
        'email': params['VERTA_SOURCE_EMAIL'],
        'devkey': params['VERTA_SOURCE_DEV_KEY'],
        'workspace': params['VERTA_SOURCE_WORKSPACE']
    },
    'dest': {
        'host': params['VERTA_DEST_HOST'],
        'email': params['VERTA_DEST_EMAIL'],
        'devkey': params['VERTA_DEST_DEV_KEY'],
        'workspace': params['VERTA_SOURCE_WORKSPACE']
    }
}


def copy_fields(fields, src, dest):
    for field in fields:
        dest[field] = src[field]


def auth_context(host, email, devkey, workspace):
    return {'headers': {'Grpc-metadata-scheme': 'https', 'Grpc-metadata-source': 'PythonClient',
                        'Grpc-metadata-email': email, 'Grpc-metadata-developer_key': devkey}, 'host': host,
            'workspace': workspace
            }


def post(auth, path, body):
    auth['headers']['Content-Type'] = 'application/json'
    body['workspaceName'] = auth['workspace']
    res = requests.post("https://{}{}".format(auth["host"], path), headers=auth['headers'], json=body)
    if res.ok:
        return res.json()
    raise Exception(res.text)


def get(auth, path):
    res = requests.get("https://{}{}".format(auth["host"], path), headers=auth['headers'])
    if res.ok:
        return res.json()
    raise Exception(res.text)


def put(auth, path, body):
    res = requests.put("https://{}{}".format(auth["host"], path), headers=auth['headers'], json=body)
    if res.ok:
        if len(res.text) > 0:
            return res.json()
        return {}
    raise Exception(res.text)


def patch(auth, path, body):
    res = requests.patch("https://{}{}".format(auth["host"], path), headers=auth['headers'], json=body)
    if res.ok:
        return res.json()
    raise Exception(res.text)


def get_endpoint(auth, endpoint):
    endpoints = post(auth, '/api/v1/deployment/endpoints', {"exactPaths": [endpoint]})
    return endpoints['endpoints'][0]


def get_endpoint_stages(auth, endpoint_id):
    path = "/api/v1/deployment/workspace/{}/endpoints/{}/stages".format(auth['workspace'], endpoint_id)
    stages = get(auth, path)
    return stages['stages']


def get_build(auth, build_id):
    path = "/api/v1/deployment/builds/{}".format(build_id)
    return get(auth, path)


def get_model_version(auth, model_version_id):
    return get(auth, '/api/v1/registry/model_versions/{}'.format(model_version_id))['model_version']


def get_registered_model(auth, registered_model_id):
    return get(auth, '/api/v1/registry/registered_models/{}'.format(registered_model_id))['registered_model']


def pp(js):
    print(json.dumps(js, indent=4))


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


def download_artifacts(auth, model_version_id, artifacts):
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


def upload_artifacts(auth, model_version_id, promoted_model):
    print("Uploading %d artifacts" % len(promoted_model['artifact_keys']))
    promoted_model['uploaded_artifacts'] = {}

    for artifact in promoted_model['artifact_keys']:
        promoted_model['uploaded_artifacts'][artifact["key"]] = upload_artifact(auth, model_version_id, artifact)


def fetch_promotion_data(_config):
    print("Fetching promotion data for '%s'" % _config['endpoint_path'])

    source = _config['source']
    source_auth = auth_context(source['host'], source['email'], source['devkey'], source['workspace'])
    endpoint = get_endpoint(source_auth, _config['endpoint_path'])
    stages = get_endpoint_stages(source_auth, endpoint['id'])

    promotion_data = {
        'endpoint': endpoint,
        'stages': []
    }

    for stage in stages:
        cr = stage['creator_request']
        promoted_stage = {'builds': []}
        copy_fields(['name', 'enable_prediction_authz'], cr, promoted_stage)
        promotion_data['stages'].append(promoted_stage)
        components = stage['components']
        for component in components:
            build_id = component['build_id']
            promoted_build = {'id': build_id}
            promoted_stage['builds'].append(promoted_build)

            build = get_build(source_auth, build_id)
            location = build['location']
            promoted_build['location'] = location

            model_version_id = build['creator_request']['model_version_id']
            promoted_model = {'model_version_id': model_version_id}
            promoted_build['model'] = promoted_model

            model_version = get_model_version(source_auth, model_version_id)

            fields = ['environment', 'artifacts', 'attributes', 'registered_model_id', 'model', 'version',
                      'readme_text']
            copy_fields(fields, model_version, promoted_model)
            registered_model_id = model_version['registered_model_id']
            promoted_model['registered_model'] = get_registered_model(source_auth, registered_model_id)

            artifacts_and_model = model_version['artifacts']
            artifacts_and_model.append(model_version['model'])
            promoted_model['artifact_keys'] = download_artifacts(source_auth, model_version_id,artifacts_and_model)
    return promotion_data


def create_registered_model(auth, rmv):
    print("Creating registered model '%s'" % rmv['version'])
    path = '/api/v1/registry/workspaces/{}/registered_models'.format(auth['workspace'])
    rm = rmv['registered_model']

    model = {}
    fields = ['labels', 'custom_permission', 'name', 'readme_text', 'resource_visibility']
    copy_fields(fields, rm, model)
    copy_fields(['artifacts', 'attributes'], rmv, model)
    return post(auth, path, model)['registered_model']


def create_registered_model_version(auth, registered_model, promoted_model):
    print("Creating model version for model '%s'" % promoted_model['version'])
    path = '/api/v1/registry/registered_models/{}/model_versions'.format(registered_model['id'])
    model_version = {
        'labels': registered_model['labels'],
    }

    # model and artifacts omitted for patching after upload
    fields = ['artifacts', 'attributes', 'environment', 'version', 'readme_text']
    copy_fields(fields, promoted_model, model_version)
    return post(auth, path, model_version)['model_version']


def update_registered_model_version(auth, registered_model_id, model_version_id, model):
    print("Updating model artifact for model version '%s'" % model_version_id)

    path = '/api/v1/registry/registered_models/{}/model_versions/{}'.format(registered_model_id, model_version_id)
    update = {'model': model['model']}
    del update['model']['path']
    return patch(auth, path, update)['model_version']


def create_endpoint(auth, promoted_endpoint):
    print("Creating endpoint '%s'" % promoted_endpoint['path'])
    path = '/api/v1/deployment/workspace/{}/endpoints'.format(auth['workspace'])
    endpoint = {}
    copy_fields(['custom_permission', 'path', 'resource_visibility', 'visibility'], promoted_endpoint, endpoint)
    return post(auth, path, endpoint)


def create_endpoint_stage(auth, endpoint, stage):
    print("Creating endpoint stage '%s'" % stage['name'])

    path = '/api/v1/deployment/workspace/{}/endpoints/{}/stages'.format(auth['workspace'], endpoint['id'])
    endpoint_stage = {
            'enable_prediction_authz': stage['enable_prediction_authz'],
            'name': stage['name']
        }
    return post(auth, path, endpoint_stage)


def create_build(auth, model_version_id):
    print("Creating build of model version '%s'" % model_version_id)
    path = '/api/v1/deployment/workspace/{}/builds'.format(auth['workspace'])
    build = {'model_version_id': int(model_version_id)}
    return post(auth, path, build)


def update_stage(auth, endpoint, stage, build):
    print("Rolling out build '%d' to '%s'" % (build['id'], endpoint['creator_request']['path']))
    path = '/api/v1/deployment/workspace/{}/endpoints/{}/stages/{}/update'.format(auth['workspace'], endpoint['id'],
                                                                                  stage['id'])
    update = {
        "build_id": build['id'],
        "strategy": "rollout"
    }
    ret = put(auth, path, update)
    return ret


def create_promoted_endpoint(_config, promotion_data):
    print("Starting promotion of '%s'" % _config['endpoint_path'])

    dest = _config['dest']
    dest_auth = auth_context(dest['host'], dest['email'], dest['devkey'], dest['workspace'])

    endpoint = create_endpoint(dest_auth, promotion_data['endpoint']['creator_request'])

    print("Created endpoint %d" % endpoint['id'])

    for promoted_stage in promotion_data['stages']:
        print("Promoting endpoint stage '%s'" % promoted_stage['name'])
        stage = create_endpoint_stage(dest_auth, endpoint, promoted_stage)
        for promoted_build in promoted_stage['builds']:
            print("Promoting source build id %d" % promoted_build['id'])
            promoted_model = promoted_build['model']
            registered_model = create_registered_model(dest_auth, promoted_model)
            registered_model_version = create_registered_model_version(dest_auth, registered_model, promoted_model)
            upload_artifacts(dest_auth, registered_model_version['id'], promoted_model)
            update_registered_model_version(dest_auth, registered_model['id'], registered_model_version['id'], promoted_model)
            build = create_build(dest_auth, registered_model_version['id'])
            update_stage(dest_auth, endpoint, stage, build)


def promote(_config):
    promotion_data = fetch_promotion_data(_config)
    create_promoted_endpoint(_config, promotion_data)
    print("Promotion complete")


promote(config)
