# Multi-Agent Support Triage on Azure AI Foundry

This repository provides a complete, end-to-end example of how to design, build, and deploy a production-ready multi-agent solution on Azure, leveraging Azure AI Foundry Agent Service and connected agents.

We will recreate a ticket-triage system in which a primary agent delegates to three specialists: priority, team assignment, and effort estimation. Then, we will map it to a reference architecture and walk through deployment choices so you can ship it for real workloads.

This repository automates the scenario by provisioning Azure infrastructure with Bicep, deploying a FastAPI container to Azure Container Apps, and wiring the app to a multi-agent workflow in Azure AI Foundry.

The solution coordinates four agents:

| Agent | Role | Output |
|-------|------|--------|
| Priority | Classifies urgency (High / Medium / Low) | e.g., “High” |
| Team | Suggests the owning team | e.g., “Infra” |
| Effort | Estimates delivery effort with supporting rationale | e.g., “Medium – provide remediation steps” |
| Triage | Orchestrates the specialists to produce a consolidated ticket summary | e.g., “High priority • Infra • Medium effort” |

The repository adds operational conveniences that go beyond the lab handout, including automated infrastructure deployment, repeatable agent bootstrapping, rate-limit-aware verification, and a consolidated test harness.

---

## Architecture Overview

```
Azure Resource Group (azd-multiagent)
├─ Azure Container Apps Environment
│  └─ Container App (FastAPI triage API)
│     ├─ Managed Identity
│     └─ Azure Container Registry image
├─ Azure Container Registry
└─ Azure AI Foundry Project
	├─ GPT-4o model deployment (capacity configurable)
	├─ Project connection (AAD)
	└─ Multi-agent graph (Priority, Team, Effort, Triage)
```

**Infrastructure as Code**: `infra/main.bicep` composes individual modules for the container app (`infra/modules/containerapp.bicep`), Azure AI Foundry resources (`infra/modules/foundry.bicep`), and container registry (`infra/modules/acr.bicep`).

**Application**: `src/api/app.py` hosts FastAPI endpoints that expose the triage capability. Environment variables emitted by the Bicep deployment provide the AI project endpoint and agent IDs.

**Automation scripts**:

- `scripts/bootstrap_agents.py` – creates or refreshes the specialist + triage agents and persists their IDs to the current `azd` environment.
- `scripts/verify_agent.py` – verifies a single agent run with retry/backoff controls.
- `scripts/test_all_agents.py` – runs all four agents in one command; automatically loads environment values from `.azure/<env>/.env`.
- `scripts/bootstrap_agents.py` + `scripts/test_all_agents.py` supersede the manual Cloud Shell steps from the learning path.

---

## Repository Layout

```
├─ azure.yaml                  # azd template metadata
├─ infra/
│  ├─ main.bicep               # top-level infrastructure composition
│  └─ modules/
│     ├─ containerapp.bicep    # Azure Container Apps + env vars
│     ├─ foundry.bicep         # Azure AI Foundry project + GPT-4o deployment
│     └─ acr.bicep             # Azure Container Registry
├─ src/
│  └─ api/
│     ├─ app.py                # FastAPI app exposing triage API
│     ├─ dockerfile            # Container image definition
│     └─ requirements.txt      # API dependencies
└─ scripts/
	├─ bootstrap_agents.py      # Creates the four agents and stores IDs
	├─ verify_agent.py          # Checks individual agent runs with retries
	└─ test_all_agents.py       # Aggregated agent test harness
```

---

## Prerequisites

1. **Azure subscription** with access to GPT-4o capacity in Azure AI Foundry.
2. **Azure Developer CLI (azd)** v1.9+ and the Azure CLI (`az`) installed locally.
3. **Python 3.12+** with `pip` available on your development machine.
4. **Docker** (builds the API image if you make code changes).
5. Sign in with `az login` before running any deployment commands.

> ℹ️ The lab document recommends manually creating the project and agents. This repository automates those steps; no Cloud Shell edits are necessary.

---

## Quick Start

### 1. Provision Infrastructure

From the repository root:

```pwsh
azd up
```

This command:

- Creates the Azure resource group and supporting resources.
- Deploys the FastAPI container image to Azure Container Apps.
- Provisions an Azure AI Foundry project, connection, and GPT-4o deployment (default capacity = 2, adjustable via `modelSkuCapacity`).

At the end of the run, `azd` populates `.azure/<env>/.env` with output values including:

- `AIFOUNDRY_PROJECT_ENDPOINT`
- `projectEndpoint` (camelCase alias)
- `AZURE_CONTAINER_REGISTRY_ENDPOINT`
- Container app URL (`apiUrl`)

### 2. Bootstrap the Agents

```pwsh
python scripts/bootstrap_agents.py
```

This script waits for DNS propagation, creates the **priority**, **team**, **effort**, and **triage** agents, and saves their IDs to the current `azd` environment:

- `PRIORITY_AGENT_ID`
- `TEAM_AGENT_ID`
- `EFFORT_AGENT_ID`
- `TRIAGE_AGENT_ID`

### 3. Test All Agents at Once

```pwsh
python scripts/test_all_agents.py --ticket "VPN outage affecting finance team"
```

`test_all_agents.py` automatically loads `.azure/<env>/.env`, maps the `projectEndpoint` alias if necessary, and prints the response from each agent. Pass `--env-file` to point at a different environment snapshot.

Example output:

```
[PRIORITY]
[MessageRole.AGENT] High

[TEAM]
[MessageRole.AGENT] Infra ...

[EFFORT]
[MessageRole.AGENT] VPN outage remediation steps ...

[TRIAGE]
[MessageRole.AGENT] High priority • Infra • Moderate effort ...
```

### 4. (Optional) Verify Individual Agents

To test a single agent with granular retry controls:

```pwsh
python scripts/verify_agent.py `
  --agent-id $Env:TRIAGE_AGENT_ID `
  --ticket "VPN outage affecting finance team" `
  --max-attempts 12 `
  --initial-backoff 12 `
  --max-backoff 60 `
  --show-transcript
```

Use this command when debugging rate-limit behaviour or inspecting transcripts in detail.

---

## Alignment with the Lab Guide

The official instructions walk through four phases, each of which maps to automation in this repo:

| Lab Section | Manual Step | Repository Equivalent |
|-------------|-------------|------------------------|
| Create an Azure AI Foundry project | Portal-based project creation, GPT-4o deployment | `infra/modules/foundry.bicep` (deployed by `azd up`) |
| Create an AI Agent client app – Prepare environment | Clone repo, set up Python environment | Included in this repo; no Cloud Shell setup needed |
| Create AI agents | Manually edit `agent_triage.py` | `scripts/bootstrap_agents.py` & `scripts/test_all_agents.py` automate agent creation and testing |
| Sign into Azure and run the app | Run `python agent_triage.py` interactively | FastAPI service + verification scripts provide automated and API-based execution |

If you’re following the lab for certification prep, you can use this repository to accelerate the “build” phase, then compare outputs against the step-by-step guide.

---

## Deploying Updates

1. **Modify application code** (e.g., update `src/api/app.py`).
2. Rebuild and redeploy:

	```pwsh
	azd deploy
	```

3. Re-run `python scripts/bootstrap_agents.py` whenever you change instructions or tear down the AI project resources.

---

## Cleanup

To remove all resources and avoid charges:

```pwsh
azd down
```

Alternatively, delete the resource group from the Azure portal (mirroring the “Clean up” section in the Microsoft Learn instructions).

---

## Troubleshooting

- **Rate limits**: Increase `modelSkuCapacity` in `infra/modules/foundry.bicep` or adjust retry flags (`--max-attempts`, `--initial-backoff`, `--max-backoff`) on the verification scripts.
- **Agent not found**: Run `python scripts/bootstrap_agents.py` to refresh the agent IDs after redeployments or project resets.
- **Environment variables missing**: Ensure `.azure/<env>/.env` exists. You can supply an explicit file with `--env-file`.
- **Authentication errors**: Run `az login` and, if using managed identity locally, ensure you have access to the AI project.

---

## Additional Resources

- [Develop a multi-agent solution – Microsoft Learn lab](https://microsoftlearning.github.io/mslearn-ai-agents/Instructions/03b-build-multi-agent-solution.html)
- [Azure AI Foundry SDK documentation](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/sdk-overview)
- [Azure AI Agent Service overview](https://learn.microsoft.com/azure/ai-services/openai/how-to/agents-overview)

Feel free to extend the project with additional agents, integrate telemetry, or adapt the infrastructure modules for your organization’s deployment process.

