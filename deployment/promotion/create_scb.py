#!/usr/bin/env python

import requests
import os
import sys
from typing import List
from verta import Client

USAGE = f"Usage: python {sys.argv[0]} [--help]  model_version_id\n\
    \n\tmodel_version_id: the model version id used to create a self contained build"


def validate(args: List[str]):
    if args[0].isdigit():
        return int(args[0])
    print("Argument must be an integer model version id")
    raise SystemExit(USAGE)


def create_build(model_version_id: int, workspace_name: str):
    r = requests.post(f"https://{os.environ['VERTA_HOST']}/api/v1/deployment/workspace/{workspace_name}/builds",
                      json={"model_version_id": model_version_id, "self_contained": True},
                      headers={'accept': 'application/json', 'Content-Type': 'application/json', 'Grpc-Metadata-source': 'PythonClient', 'Grpc-Metadata-email': f"{os.environ['VERTA_EMAIL']}", 'Grpc-Metadata-developer_key': f"{os.environ['VERTA_DEV_KEY']}"})
    # TODO: retry?
    if r.status_code != 200:
        raise SystemError(f"creating a build of model version {model_version_id} failed with code: {r.status_code} and message: {r.content}")

    build = r.json()
    return build['id']


def main(model_version_id: int):
    client = Client()
    workspace = client.get_workspace()
    build_id = create_build(model_version_id, workspace)
    print(f"Started self contained build {build_id}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(USAGE)

    if args[0] == "--help":
        print(USAGE)
    else:
        arguments = validate(args)
        main(arguments)
