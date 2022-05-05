import dataclasses
import os
import requests
import sys
from typing import List

from verta import Client


USAGE = f"Usage: python {sys.argv[0]} [--help] | build_id external_scan_results_file\n \
    \n\tbuild_id: the build with which to associate the results \
    \n\texternal_scan_results_file: file with the results of the external scan"

@dataclasses.dataclass
class Arguments:
    build_id: int
    external_scan_results_file: str


def validate(args: List[str]):
    # Convert build_id to int
    if not args[0].isdigit():
        raise SystemExit("Type Error: build_id must be an int")
    args[0] = int(args[0])
    try:
        arguments = Arguments(*args)
    except TypeError:
        raise SystemExit(USAGE)
    return arguments


def save_scan_results(build_id: int, scan_results: str, workspace_name: str):
    print(f"saving scan results for build {build_id}")
    r = requests.put(f"https://{os.environ['VERTA_HOST']}/api/v1/deployment/workspace/{workspace_name}/builds/{build_id}/scan", \
        data=f"{{ \"scan_status\": \"scanned\", \"scan_external_results\": \"{scan_results}\"}}", \
        headers={'accept': 'application/json', 'Content-Type': 'application/json', 'Grpc-Metadata-source': 'PythonClient', 'Grpc-Metadata-email': f"{os.environ['VERTA_EMAIL']}", 'Grpc-Metadata-developer_key': f"{os.environ['VERTA_DEV_KEY']}"})

    if r.status_code != 200:
        raise SystemError(f"saving scan results failed with code: {r.status_code} and message: {r.content}")
    
    print("success")


def main(arguments: Arguments):
    client = Client()
    workspace_name = client.get_workspace()
    f = open(arguments.external_scan_results_file)
    # I'm bravely reading all at once because it better not be TOO much data or we won't be able to pass it to dep-api anyway
    scan_results = f.read().strip()
    save_scan_results(arguments.build_id, scan_results, workspace_name)

    f.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(USAGE)

    if args[0] == "--help":
        print(USAGE)
    else:
        arguments = validate(args)
        main(arguments)
