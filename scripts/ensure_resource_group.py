import json
import os
import subprocess
import sys
from typing import List


def run_command(command: List[str]) -> subprocess.CompletedProcess:
    """Execute a command and return the completed process."""
    if os.name == "nt":
        joined = " ".join(command)
        return subprocess.run(joined, capture_output=True, text=True, shell=True)
    return subprocess.run(command, capture_output=True, text=True)


def ensure_resource_group() -> None:
    resource_group = os.getenv("AZURE_RESOURCE_GROUP") or "azd-multiagent"
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    location = os.getenv("AZURE_LOCATION") or "westus3"

    show_cmd = ["az", "group", "show", "--name", resource_group]
    if subscription_id:
        show_cmd.extend(["--subscription", subscription_id])

    print(f"Checking for resource group '{resource_group}'...")
    show_result = run_command(show_cmd)

    if show_result.returncode == 0:
        print(f"Resource group '{resource_group}' already exists. Skipping creation.")
        return

    print(f"Resource group '{resource_group}' not found. Creating in location '{location}'.")
    create_cmd = ["az", "group", "create", "--name", resource_group, "--location", location]
    if subscription_id:
        create_cmd.extend(["--subscription", subscription_id])

    create_result = run_command(create_cmd)
    if create_result.returncode != 0:
        sys.stderr.write(create_result.stderr)
        raise SystemExit(create_result.returncode)

    try:
        details = json.loads(create_result.stdout or "{}")
    except json.JSONDecodeError:
        details = {}

    if details.get("properties", {}).get("provisioningState") == "Succeeded":
        print(f"Resource group '{resource_group}' created successfully.")
    else:
        print(f"Resource group '{resource_group}' ensured (status unknown).")


if __name__ == "__main__":
    ensure_resource_group()
