param(
    [int]$DnsTimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "Installing bootstrap dependencies..."
python -m pip install --quiet --disable-pip-version-check -r "$PSScriptRoot/../src/api/requirements.txt"

Write-Host "Resolving AI Foundry endpoint..."
$projectEndpoint = (azd env get-value projectEndpoint 2>$null).Trim()
if ([string]::IsNullOrWhiteSpace($projectEndpoint)) {
    $accountName = (azd env get-value accountName 2>$null).Trim()
    $projectName = (azd env get-value projectName 2>$null).Trim()

    if ([string]::IsNullOrWhiteSpace($accountName) -or [string]::IsNullOrWhiteSpace($projectName)) {
        throw "Unable to determine project endpoint. Set 'projectEndpoint' (or accountName/projectName) with 'azd env set'."
    }

    $projectEndpoint = "https://$accountName.services.ai.azure.com/api/projects/$projectName"
}

$env:AIFOUNDRY_PROJECT_ENDPOINT = $projectEndpoint
$env:AIFOUNDRY_DNS_TIMEOUT = $DnsTimeoutSeconds.ToString()

Write-Host "Bootstrapping AI Agents..."
python "$PSScriptRoot/bootstrap_agents.py"
