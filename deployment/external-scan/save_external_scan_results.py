import dataclasses
import os
import requests
import sys
from typing import List

from verta import Client


USAGE = f"Usage: python {sys.argv[0]} [--help] | build_id url safety_status \n \
    \n\tbuild_id: the build with which to associate the results \
    \n\turl: url to scan results \
    \n\tsafety_status: [safe, unsafe] whether the scan ultimately passed (safe) or failed (unsafe)"

@dataclasses.dataclass
class Arguments:
    build_id: int
    url: str
    safety_status: str


def validate(args: List[str]):
    # Convert build_id to int
    if not args[0].isdigit():
        raise SystemExit("Type Error: build_id must be an int")
    args[0] = int(args[0])
    if args[2] != "safe" and args[2] != "unsafe":
        raise SystemExit("Type Error: safety_status must be 'safe' or 'unsafe'")
    try:
        arguments = Arguments(*args)
    except TypeError:
        raise SystemExit(USAGE)
    return arguments


def save_scan_results(build_id: int, url: str, safety_status: str, workspace_name: str):
    print(f"saving scan results for build {build_id}")
    r = requests.put(f"https://{os.environ['VERTA_HOST']}/api/v1/deployment/workspace/{workspace_name}/builds/{build_id}/scan", \
        data=f"{{ \"scan_status\": \"scanned\", \"scan_external_results\": {{\"url\": \"{url}\", \"safety_status\": \"{safety_status}\"}}}}", \
        headers={'accept': 'application/json', 'Content-Type': 'application/json', 'Grpc-Metadata-source': 'PythonClient', 'Grpc-Metadata-email': f"{os.environ['VERTA_EMAIL']}", 'Grpc-Metadata-developer_key': f"{os.environ['VERTA_DEV_KEY']}"})

    if r.status_code != 200:
        raise SystemError(f"saving scan results failed with code: {r.status_code} and message: {r.content}")
    
    print("success")


def main(arguments: Arguments):
    client = Client()
    workspace_name = client.get_workspace()
    save_scan_results(arguments.build_id, arguments.url, arguments.safety_status, workspace_name)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(USAGE)

    if args[0] == "--help":
        print(USAGE)
    else:
        arguments = validate(args)
        main(arguments)
