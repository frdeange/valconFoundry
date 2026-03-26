"""
Demo 2e — Agent with MCP tools registered as Foundry Project Connections

Unlike Demo 2d (where MCP servers are connected inline in code), this demo
uses MCP tools that were pre-configured in the Foundry portal as Project
Connections. This is the recommended approach for production because:

  - Tools are managed centrally in the portal (no code changes to add/remove)
  - Authentication is handled by the connection (managed identity, API keys, OAuth)
  - The same tool can be shared across multiple agents in the project
  - IT/admins can control which tools are available via RBAC

The two tools used here were created in the Foundry portal:
  1. MSLearnMCP  — Microsoft Learn documentation search
  2. WorkIQMail — Microsoft 365 Copilot agent

To create your own MCP connections in the portal:
  Foundry Portal → Management Center → Connected resources → + New connection
  → Select "MCP" → Enter server URL → Save

Key difference vs Demo 2d:
  Demo 2d:  MCPTool(server_url="https://...", server_label="...")
  Demo 2e:  MCPTool(server_label="...", project_connection_id="<connection-id>",
                     server_url="<target-url>", require_approval="never")
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-portal-mcp-agent"

# Connection names as they appear in the Foundry portal
MSLEARN_CONNECTION = "MSLearnMCP"
WORKIQ_CONNECTION = "WorkIQMail"


def main():
    print("=" * 60)
    print("DEMO 2e — Agents with Portal-Registered MCP Tools")
    print("=" * 60)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        # ── List available MCP connections ──────────────────────
        print("\n📋 MCP tools registered in Foundry portal:")
        for name in [MSLEARN_CONNECTION, WORKIQ_CONNECTION]:
            conn = project_client.connections.get(name, include_credentials=False)
            print(f"   • {conn.name}  →  {conn.target}")

        # ── Get connection details ──────────────────────────────
        learn_conn = project_client.connections.get(MSLEARN_CONNECTION, include_credentials=False)
        workiq_conn = project_client.connections.get(WORKIQ_CONNECTION, include_credentials=False)

        # ── Define MCP tools from portal connections ────────────
        # require_approval="never" — tools are pre-approved in the portal
        learn_tool = MCPTool(
            server_label="microsoft-learn",
            server_url=learn_conn.target,
            project_connection_id=learn_conn.id,
            require_approval="never",
        )
        workiq_tool = MCPTool(
            server_label="WorkIQMail",
            server_url=workiq_conn.target,
            project_connection_id=workiq_conn.id,
            require_approval="never",
        )

        with project_client.get_openai_client() as openai_client:

            # ── Create one agent with BOTH portal tools ─────────
            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a productivity assistant with access to two tools: "
                        "1) Microsoft Learn — for searching technical documentation. "
                        "2) WorkIQ Copilot — for Microsoft 365 productivity tasks like sending emails. "
                        "Choose the right tool based on the user's question."
                    ),
                    tools=[learn_tool, workiq_tool],
                ),
            )
            print(f"\n📌 Agent created: {agent.name}")
            print(f"   Tools: {MSLEARN_CONNECTION}, {WORKIQ_CONNECTION}")

            # Turn 1: Technical question → should use Microsoft Learn
            q1 = "How do hosted agents work in Microsoft Foundry?"
            print(f"\n[Q1] {q1}")

            response = openai_client.responses.create(
                input=[{"role": "user", "content": q1}],
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            print(f"\n[A1] {response.output_text}")

            # Turn 2: Action request → should use WorkIQ Copilot
            q2 = "Send an email to frdeange@microsoft.com summarizing what we just discussed about hosted agents in Foundry."
            print(f"\n[Q2] {q2}")

            response = openai_client.responses.create(
                input=[{"role": "user", "content": q2}],
                previous_response_id=response.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            print(f"\n[A2] {response.output_text}")

            print(f"\n📌 Resources preserved (agent: {agent.name})")

    print("\n✅ Demo 2e complete.")


if __name__ == "__main__":
    main()
