import os
import socket
import subprocess
import time
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ConnectedAgentTool

endpoint = os.environ["AIFOUNDRY_PROJECT_ENDPOINT"]
default_host = os.environ.get("AIFOUNDRY_ACCOUNT_HOST")
agent_model = os.getenv("AIFOUNDRY_AGENT_MODEL", "gpt-4o").strip() or "gpt-4o"
credential = DefaultAzureCredential()
project_client = AIProjectClient(endpoint=endpoint, credential=credential)
agents_client = project_client.agents

def wait_for_dns(host: str, timeout: int = 900, interval: int = 10) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            socket.gethostbyname(host)
            return
        except socket.gaierror:
            print(f"Waiting for DNS propagation for {host}...", flush=True)
            time.sleep(interval)
    raise RuntimeError(f"DNS name {host} did not resolve within {timeout} seconds.")


parsed = urlparse(endpoint)
if not parsed.hostname:
    raise ValueError(f"Invalid project endpoint: {endpoint}")

# Prefer the project endpoint host (custom subdomain). Keep the legacy account host
# as a fallback for older environments or partially-provisioned setups.
bootstrap_host = parsed.hostname
fallback_host = None
if default_host:
    parsed_default = urlparse(default_host if default_host.startswith("https") else f"https://{default_host}")
    if parsed_default.hostname and parsed_default.hostname.lower() != bootstrap_host.lower():
        fallback_host = parsed_default.hostname

dns_timeout_env = os.getenv("AIFOUNDRY_DNS_TIMEOUT")
try:
    dns_timeout = int(dns_timeout_env) if dns_timeout_env else 900
except ValueError:
    dns_timeout = 900

try:
    wait_for_dns(bootstrap_host, timeout=dns_timeout)
except RuntimeError:
    if fallback_host:
        wait_for_dns(fallback_host, timeout=dns_timeout)
    else:
        raise

print(f"Provisioning agents with model: {agent_model}")

print("Creating specialist agents...")
priority = agents_client.create_agent(
    model=agent_model, name="priority", instructions="Return High/Medium/Low"
)
team = agents_client.create_agent(
    model=agent_model, name="team", instructions="Assign Frontend/Backend/Infra/Marketing"
)
effort = agents_client.create_agent(
    model=agent_model, name="effort", instructions="Estimate Small/Medium/Large"
)

print("PRIORITY_AGENT_ID:", priority.id)
print("TEAM_AGENT_ID:", team.id)
print("EFFORT_AGENT_ID:", effort.id)

connected_tools = [
    ConnectedAgentTool(
        id=priority.id,
        name=priority.name,
        description="Assesses ticket priority",
    ),
    ConnectedAgentTool(
        id=team.id,
        name=team.name,
        description="Suggests responsible team",
    ),
    ConnectedAgentTool(
        id=effort.id,
        name=effort.name,
        description="Estimates effort required",
    ),
]

print("Creating triage agent...")
triage = agents_client.create_agent(
    model=agent_model,
    name="triage",
    instructions="Coordinate priority, team, and effort via connected agents.",
    tools=[definition for tool in connected_tools for definition in tool.definitions],
)

print("TRIAGE_AGENT_ID:", triage.id)

# Store in azd env
subprocess.run(["azd", "env", "set", "TRIAGE_AGENT_ID", triage.id], check=False)
subprocess.run(["azd", "env", "set", "PRIORITY_AGENT_ID", priority.id], check=False)
subprocess.run(["azd", "env", "set", "TEAM_AGENT_ID", team.id], check=False)
subprocess.run(["azd", "env", "set", "EFFORT_AGENT_ID", effort.id], check=False)
