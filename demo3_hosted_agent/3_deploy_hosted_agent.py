"""
Demo 3 — Build, push, and deploy a Hosted Agent to Microsoft Foundry

This script automates the FULL lifecycle:
  1. Build the Docker image and push it to ACR (cloud build via ACR Tasks)
  2. Ensure the Foundry project's managed identity can pull from ACR
  3. Create the account-level capability host (if needed)
  4. Register the hosted agent version in Foundry
  5. Start the agent deployment

PREREQUISITES:
  - Azure CLI logged in (`az login`)
  - ACR_NAME, FOUNDRY_ACCOUNT_NAME, FOUNDRY_PROJECT_NAME, FOUNDRY_RESOURCE_GROUP
    set in your .env file
  - An Azure Container Registry already created
"""

import os
import sys
import json
import subprocess
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import HostedAgentDefinition, ProtocolVersionRecord, AgentProtocol

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
ACR_NAME = os.environ["ACR_NAME"]
FOUNDRY_ACCOUNT = os.environ["FOUNDRY_ACCOUNT_NAME"]
FOUNDRY_PROJECT = os.environ["FOUNDRY_PROJECT_NAME"]
RESOURCE_GROUP = os.environ["FOUNDRY_RESOURCE_GROUP"]

AGENT_NAME = "demo-hosted-agent"
IMAGE_NAME = "demo-hosted-agent"
IMAGE_TAG = "latest"
ACR_IMAGE = f"{ACR_NAME}.azurecr.io/{IMAGE_NAME}:{IMAGE_TAG}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_cmd(cmd, description, check=True):
    """Run a shell command, print output, and optionally check for errors."""
    print(f"\n{'─' * 60}")
    print(f"▶ {description}")
    print(f"  $ {cmd}")
    print(f"{'─' * 60}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        # Some Azure CLI commands write progress to stderr (not errors)
        print(result.stderr.strip())
    if check and result.returncode != 0:
        print(f"\n❌ Command failed (exit code {result.returncode})")
        sys.exit(1)
    return result


def has_docker():
    """Check if Docker CLI is available and the daemon is running."""
    result = subprocess.run("docker info", shell=True, capture_output=True, text=True)
    return result.returncode == 0


def step1_build_and_push():
    """Build the container image and push it to ACR."""
    print("\n" + "=" * 60)
    print("STEP 1: Build & push container image to ACR")
    print("=" * 60)

    if has_docker():
        # Local Docker build + push
        run_cmd(f"az acr login --name {ACR_NAME}", "Login to ACR")
        run_cmd(
            f"docker build --platform linux/amd64 -t {ACR_IMAGE} {SCRIPT_DIR}",
            "Build Docker image (linux/amd64)",
        )
        run_cmd(f"docker push {ACR_IMAGE}", "Push image to ACR")
    else:
        # Fallback: use ACR Tasks for cloud-based build (no local Docker needed)
        print("\n⚠️  Docker not available locally — using ACR Tasks (cloud build)")
        run_cmd(
            f"az acr build --registry {ACR_NAME} --resource-group {RESOURCE_GROUP} "
            f"--platform linux/amd64 --image {IMAGE_NAME}:{IMAGE_TAG} {SCRIPT_DIR}",
            "Build image in the cloud via ACR Tasks",
        )

    print(f"\n✅ Image available: {ACR_IMAGE}")


def step2_configure_rbac():
    """Ensure the Foundry project's managed identity can pull from ACR."""
    print("\n" + "=" * 60)
    print("STEP 2: Configure RBAC (ACR pull permissions)")
    print("=" * 60)

    # Get the project's managed identity principal ID
    result = run_cmd(
        f"az cognitiveservices account show "
        f"--name {FOUNDRY_ACCOUNT} --resource-group {RESOURCE_GROUP} "
        f'--query "identity.principalId" -o tsv',
        "Get Foundry managed identity",
    )
    principal_id = result.stdout.strip()

    if not principal_id or principal_id == "None":
        # Enable system-assigned managed identity if not already enabled
        print("  Enabling system-assigned managed identity...")
        run_cmd(
            f"az cognitiveservices account identity assign "
            f"--name {FOUNDRY_ACCOUNT} --resource-group {RESOURCE_GROUP}",
            "Enable managed identity",
        )
        result = run_cmd(
            f"az cognitiveservices account show "
            f"--name {FOUNDRY_ACCOUNT} --resource-group {RESOURCE_GROUP} "
            f'--query "identity.principalId" -o tsv',
            "Get managed identity (retry)",
        )
        principal_id = result.stdout.strip()

    print(f"  Principal ID: {principal_id}")

    # Get ACR resource ID
    result = run_cmd(
        f"az acr show --name {ACR_NAME} --resource-group {RESOURCE_GROUP} --query id -o tsv",
        "Get ACR resource ID",
    )
    acr_id = result.stdout.strip()

    # Assign AcrPull role (idempotent — won't fail if already assigned)
    run_cmd(
        f"az role assignment create "
        f"--assignee-object-id {principal_id} --assignee-principal-type ServicePrincipal "
        f'--role "AcrPull" --scope {acr_id}',
        "Assign AcrPull role to Foundry managed identity",
        check=False,  # May already exist
    )
    print(f"\n✅ RBAC configured: Foundry can pull from {ACR_NAME}")


def step3_capability_host():
    """Create the account-level capability host (required for hosted agents)."""
    print("\n" + "=" * 60)
    print("STEP 3: Create capability host (if needed)")
    print("=" * 60)

    # Get subscription ID
    result = run_cmd(
        'az account show --query "id" -o tsv',
        "Get current subscription ID",
    )
    sub_id = result.stdout.strip()

    url = (
        f"https://management.azure.com/subscriptions/{sub_id}"
        f"/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.CognitiveServices/accounts/{FOUNDRY_ACCOUNT}"
        f"/capabilityHosts/accountcaphost?api-version=2025-10-01-preview"
    )

    body = json.dumps({
        "properties": {
            "capabilityHostKind": "Agents",
            "enablePublicHostingEnvironment": True,
        }
    })

    run_cmd(
        f"az rest --method put --url \"{url}\" "
        f"--headers \"content-type=application/json\" "
        f"--body '{body}'",
        "Create/update capability host",
        check=False,  # May already exist or take time to propagate
    )
    print(f"\n✅ Capability host configured")


def step4_register_agent():
    """Register the hosted agent version in Foundry."""
    print("\n" + "=" * 60)
    print("STEP 4: Register hosted agent in Foundry")
    print("=" * 60)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=credential,
            allow_preview=True,
        ) as project_client,
    ):
        agent = project_client.agents.create_version(
            agent_name=AGENT_NAME,
            definition=HostedAgentDefinition(
                container_protocol_versions=[
                    ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="v1")
                ],
                cpu="1",
                memory="2Gi",
                image=ACR_IMAGE,
                environment_variables={
                    "AZURE_AI_PROJECT_ENDPOINT": PROJECT_ENDPOINT,
                    "AZURE_AI_MODEL_DEPLOYMENT_NAME": MODEL,
                },
            ),
        )

        print(f"\n📌 Hosted Agent registered:")
        print(f"   Name:    {agent.name}")
        print(f"   ID:      {agent.id}")
        print(f"   Version: {agent.version}")
        print(f"   Image:   {ACR_IMAGE}")

    return agent


def step5_start_agent(agent):
    """Start the hosted agent deployment."""
    print("\n" + "=" * 60)
    print("STEP 5: Start agent deployment")
    print("=" * 60)

    result = run_cmd(
        f"az cognitiveservices agent start "
        f"--account-name {FOUNDRY_ACCOUNT} --project-name {FOUNDRY_PROJECT} "
        f"--name {AGENT_NAME} --agent-version {agent.version} "
        f"--min-replicas 0 --max-replicas 1",
        "Start the hosted agent deployment (scale-to-zero when idle)",
        check=False,  # CLI extension may not be installed
    )

    if result.returncode != 0:
        print(f"\n⚠️  The 'az cognitiveservices agent' CLI extension may not be installed.")
        print(f"   You can start the agent from the Foundry portal or install the extension:")
        print(f"     az extension add --name ai-foundry")
        print(f"   Then retry:")
        print(f"     az cognitiveservices agent start \\")
        print(f"       --account-name {FOUNDRY_ACCOUNT} --project-name {FOUNDRY_PROJECT} \\")
        print(f"       --name {AGENT_NAME} --agent-version {agent.version}")
    else:
        print(f"\n🚀 Agent deployment initiated.")

    print(f"\n   Check status in the Foundry portal or via CLI.")
    print(f"\n   Invoke it like any other agent:")
    print(f"     openai_client.responses.create(")
    print(f'       extra_body={{"agent_reference": {{"name": "{AGENT_NAME}", "type": "agent_reference"}}}}')
    print(f"     )")


def main():
    print("=" * 60)
    print("DEMO 3 — Full Hosted Agent Pipeline")
    print(f"  ACR:     {ACR_NAME}.azurecr.io")
    print(f"  Image:   {ACR_IMAGE}")
    print(f"  Account: {FOUNDRY_ACCOUNT}")
    print(f"  Project: {FOUNDRY_PROJECT}")
    print("=" * 60)

    step1_build_and_push()
    step2_configure_rbac()
    step3_capability_host()
    agent = step4_register_agent()
    step5_start_agent(agent)

    print("\n" + "=" * 60)
    print("✅ Demo 3 complete — full pipeline executed")
    print("=" * 60)


if __name__ == "__main__":
    main()
