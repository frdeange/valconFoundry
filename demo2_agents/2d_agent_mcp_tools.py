"""
Demo 2d — Agent with MCP (Model Context Protocol) tools

This demo shows how to connect an agent to an external MCP server.
MCP is a standard protocol that lets agents access tools hosted on remote
servers — no local function code needed.

We use the Microsoft Learn MCP server (https://learn.microsoft.com/api/mcp)
to let the agent search and retrieve Microsoft documentation.

Key points:
  - MCPTool just needs a server_url and a label — no local function code
  - The agent discovers available tools from the MCP server automatically
  - MCP calls may require approval (require_approval="never"|"always")
  - When require_approval="always", you must handle mcp_approval_request
    items in the response and send back approval responses

IMPORTANT: MCP tools run SERVER-SIDE in Foundry. Your code does NOT call the
MCP server directly — the agent service does it for you.
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-mcp-agent"


def handle_mcp_approval(response, openai_client, agent_name, depth=0, max_depth=10):
    """
    Handle MCP approval requests — auto-approve for demo purposes.
    When require_approval="always", the agent pauses before calling MCP tools.
    """
    if depth >= max_depth:
        print(f"  ⚠️  Max approval rounds ({max_depth}) reached.")
        return response

    approval_requests = [
        item for item in response.output if item.type == "mcp_approval_request"
    ]
    if not approval_requests:
        return response

    approvals = []
    for req in approval_requests:
        print(f"  🔐 MCP tool call: {req.server_label} → {req.name}")
        if req.arguments:
            print(f"     Args: {req.arguments}")
        approvals.append({
            "type": "mcp_approval_response",
            "approval_request_id": req.id,
            "approve": True,
        })

    response = openai_client.responses.create(
        input=approvals,
        previous_response_id=response.id,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
    )
    return handle_mcp_approval(response, openai_client, agent_name, depth + 1, max_depth)


def main():
    print("=" * 60)
    print("DEMO 2d — Agent with MCP (Model Context Protocol) Tool")
    print("=" * 60)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            # Define the MCP tool pointing to Microsoft Learn
            learn_mcp = MCPTool(
                server_label="microsoft-learn",
                server_url="https://learn.microsoft.com/api/mcp",
                require_approval="always",
            )

            # Create agent with the MCP tool
            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a technical assistant that helps developers find "
                        "information in Microsoft documentation. "
                        "Use the Microsoft Learn MCP tool to search for and retrieve "
                        "documentation when answering technical questions. "
                        "Always cite the source URL in your response."
                    ),
                    tools=[learn_mcp],
                ),
            )
            print(f"\n📌 Agent created: {agent.name} (with Microsoft Learn MCP)")

            question = "How do I create an agent using the Azure AI Foundry SDK v2 in Python?"
            print(f"\n[Q] {question}")

            response = openai_client.responses.create(
                input=[{"role": "user", "content": question}],
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            response = handle_mcp_approval(response, openai_client, agent.name)
            print(f"\n[A] {response.output_text}")

            print(f"\n📌 Resources preserved (agent: {agent.name})")

    print("\n✅ Demo 2d complete.")


if __name__ == "__main__":
    main()
