import dataclasses
import datetime
import os
import requests
import sys
import time
from typing import List

from verta import Client


USAGE = f"Usage: python {sys.argv[0]} [--help] | model_version_id [docker-context-output-directory]\n\
    \n\tmodel_version_id: the model version ID to build\
    \n\tdocker-context-output-directory: directory to save docker context into; defaults to current directory"

@dataclasses.dataclass
class Arguments:
    model_version_id: int
    docker_context_output_directory: str


def validate(args: List[str]):
    # Convert model_version_id to int
    if not args[0].isdigit():
        raise SystemExit("Type Error: model_version_id must be an int")
    args[0] = int(args[0])
    # Default location is current directory
    if len(args) == 1:
        args.append(".")
    try:
        arguments = Arguments(*args)
    except TypeError:
        raise SystemExit(USAGE)
    return arguments


def make_build_external(build_id: int, workspace_name: str):
    print(f"marking build as externally scanned")
    r = requests.post(f"https://{os.environ['VERTA_HOST']}/api/v1/deployment/workspace/{workspace_name}/builds/{build_id}/scan", \
        data="{ \"scan_external\": true }", \
        headers={'accept': 'application/json', 'Content-Type': 'application/json', 'Grpc-Metadata-source': 'PythonClient', 'Grpc-Metadata-email': f"{os.environ['VERTA_EMAIL']}", 'Grpc-Metadata-developer_key': f"{os.environ['VERTA_DEV_KEY']}"})

    if r.status_code != 200:
        raise SystemError(f"marking build as external failed with code: {r.status_code} and message: {r.content}")



def get_build(build_id: int, workspace_name: str):
    r = requests.get(f"https://{os.environ['VERTA_HOST']}/api/v1/deployment/workspace/{workspace_name}/builds/{build_id}", \
        headers={'accept': 'application/json', 'Content-Type': 'application/json', 'Grpc-Metadata-source': 'PythonClient', 'Grpc-Metadata-email': f"{os.environ['VERTA_EMAIL']}", 'Grpc-Metadata-developer_key': f"{os.environ['VERTA_DEV_KEY']}"})
    # TODO: retry?
    if r.status_code != 200:
        raise SystemError(f"fetching build {build_id} failed with code: {r.status_code} and message: {r.content}")
    return r.json()
    

def create_build(model_version_id: int, workspace_name: str):
    print(f"creating build for model version {model_version_id}")
    r = requests.post(f"https://{os.environ['VERTA_HOST']}/api/v1/deployment/workspace/{workspace_name}/builds", \
        data=f"{{ \"model_version_id\": {model_version_id}, \"self_contained\": true}}", \
        headers={'accept': 'application/json', 'Content-Type': 'application/json', 'Grpc-Metadata-source': 'PythonClient', 'Grpc-Metadata-email': f"{os.environ['VERTA_EMAIL']}", 'Grpc-Metadata-developer_key': f"{os.environ['VERTA_DEV_KEY']}"})

    if r.status_code != 200:
        raise SystemError(f"creating build failed with code: {r.status_code} and message: {r.content}")

    build_id = r.json()["id"]
    print(f"success; build ID is {build_id}")
    return build_id


def main(arguments: Arguments):
    client = Client()
    workspace_name = client.get_workspace()
    # Create build
    build_id = create_build(arguments.model_version_id, workspace_name)
    # Mark build as externally scanned
    make_build_external(build_id, workspace_name)

    # Fetch docker context
    print("downloading docker context")
    model_version = client.get_registered_model_version(arguments.model_version_id)
    dt_string = datetime.datetime.now().strftime("%m-%d-%Y-%H-%M-%S")
    docker_context_filename = "mv" + str(arguments.model_version_id) + "-" + "build" + str(build_id) + "-"  + dt_string + ".tgz"
    model_version.download_docker_context(arguments.docker_context_output_directory + "/" + docker_context_filename, self_contained=True)

    print("waiting for build...", end="")
    sys.stdout.flush()
    build_json = get_build(build_id, workspace_name)
    # Wait for completed build status
    while not build_json["status"] in ("finished", "error"):
        print(".", end="")
        sys.stdout.flush()
        time.sleep(5)
        build_json = get_build(build_id, workspace_name)

    if build_json["status"] == "error":
        print()
        raise RuntimeError(f"build {build_id} failed with message: {build_json['message']}")

    build_location = build_json["location"]
    print()
    print()
    print("build complete; image location:")
    print(build_location)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(USAGE)

    if args[0] == "--help":
        print(USAGE)
    else:
        arguments = validate(args)
        main(arguments)
