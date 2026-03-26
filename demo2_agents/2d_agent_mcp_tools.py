"""
Demo 2d — Agent with MCP (Model Context Protocol) tools

This demo shows how to connect an agent to external MCP servers.
MCP is a standard protocol that lets agents access tools hosted on remote
servers — no local function code needed.

We use TWO public MCP servers to showcase the concept:
  1. Microsoft Learn MCP (https://learn.microsoft.com/api/mcp)
     → Lets the agent search and retrieve Microsoft documentation
  2. GitMCP (https://gitmcp.io)
     → Turns any GitHub repo into an MCP server

Key points:
  - MCPTool just needs a server_url and a label — no local function code
  - The agent discovers available tools from the MCP server automatically
  - MCP calls may require approval (require_approval="never"|"always")
  - When require_approval="always", you must handle mcp_approval_request
    items in the response and send back McpApprovalResponse

IMPORTANT: MCP tools run SERVER-SIDE in Foundry. Your code does NOT call the
MCP server directly — the agent service does it for you.
"""

import os
import json
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-mcp-agent"


def handle_mcp_approval(response, openai_client, conversation_id, agent_name):
    """
    Handle MCP approval requests.
    When require_approval="always", the agent pauses and asks for permission
    before calling MCP tools. We auto-approve here for demo purposes.
    """
    approval_requests = [
        item for item in response.output if item.type == "mcp_approval_request"
    ]
    if not approval_requests:
        return response

    approvals = []
    for req in approval_requests:
        print(f"  🔐 MCP approval requested: {req.server_label} → {req.method}")
        print(f"     Arguments: {json.dumps(req.arguments) if hasattr(req, 'arguments') else 'N/A'}")
        approvals.append({
            "type": "mcp_approval_response",
            "request_id": req.id,
            "approve": True,
        })
        print(f"     ✅ Auto-approved")

    # Send approvals back and get the actual response
    response = openai_client.responses.create(
        conversation=conversation_id,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
        input=approvals,
    )
    # Recurse in case there are more approval requests
    return handle_mcp_approval(response, openai_client, conversation_id, agent_name)


def demo_microsoft_learn_mcp():
    """Demo using Microsoft Learn MCP server to search documentation."""
    print("\n" + "=" * 60)
    print("PART 1: Microsoft Learn MCP")
    print("Agent can search and read Microsoft documentation")
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
                agent_name=AGENT_NAME + "-learn",
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

            # Create conversation and ask a question
            conversation = openai_client.conversations.create()

            question = "How do I create an agent using the Azure AI Foundry SDK v2 in Python?"
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": question}],
            )
            print(f"\n[Q] {question}")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )

            # Handle MCP approval requests
            response = handle_mcp_approval(response, openai_client, conversation.id, agent.name)
            print(f"\n[A] {response.output_text}")

            # Follow-up question
            question2 = "What built-in tools are available for Foundry agents?"
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": question2}],
            )
            print(f"\n[Q] {question2}")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            response = handle_mcp_approval(response, openai_client, conversation.id, agent.name)
            print(f"\n[A] {response.output_text}")

            # Resources kept for portal demo
            # openai_client.conversations.delete(conversation_id=conversation.id)
            # project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            print(f"\n📌 Resources preserved (agent: {agent.name})")


def demo_gitmcp():
    """Demo using GitMCP to give the agent context from a GitHub repo."""
    print("\n" + "=" * 60)
    print("PART 2: GitMCP — GitHub Repository as MCP Server")
    print("Agent can read and understand any public GitHub repo")
    print("=" * 60)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            # GitMCP: just replace github.com with gitmcp.io in any repo URL
            # Example: the Azure AI Projects SDK repo
            gitmcp = MCPTool(
                server_label="azure-sdk-repo",
                server_url="https://gitmcp.io/Azure/azure-sdk-for-python",
                require_approval="always",
            )

            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME + "-gitmcp",
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a code assistant that helps developers understand "
                        "open-source projects. Use the GitMCP tool to read repository "
                        "documentation and code structure. Be concise and specific."
                    ),
                    tools=[gitmcp],
                ),
            )
            print(f"\n📌 Agent created: {agent.name} (with GitMCP)")

            conversation = openai_client.conversations.create()

            question = "What is the azure-ai-projects package and what are its main features?"
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": question}],
            )
            print(f"\n[Q] {question}")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            response = handle_mcp_approval(response, openai_client, conversation.id, agent.name)
            print(f"\n[A] {response.output_text}")

            # Resources kept for portal demo
            # openai_client.conversations.delete(conversation_id=conversation.id)
            # project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            print(f"\n📌 Resources preserved (agent: {agent.name})")


def demo_multiple_mcp():
    """Demo combining multiple MCP servers in a single agent."""
    print("\n" + "=" * 60)
    print("PART 3: Multi-MCP Agent — Combining multiple MCP servers")
    print("Agent uses BOTH Microsoft Learn AND GitMCP simultaneously")
    print("=" * 60)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            # Combine both MCP tools in one agent
            learn_mcp = MCPTool(
                server_label="microsoft-learn",
                server_url="https://learn.microsoft.com/api/mcp",
                require_approval="always",
            )
            gitmcp = MCPTool(
                server_label="foundry-samples-repo",
                server_url="https://gitmcp.io/microsoft-foundry/foundry-samples",
                require_approval="always",
            )

            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME + "-multi",
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a Microsoft Foundry expert assistant. You have access to: "
                        "1) Microsoft Learn documentation (use for concepts, how-to guides, API reference) "
                        "2) The Foundry Samples GitHub repo (use for code examples and sample implementations). "
                        "When answering, combine official docs with real code examples when possible."
                    ),
                    tools=[learn_mcp, gitmcp],
                ),
            )
            print(f"\n📌 Agent created: {agent.name} (with Learn MCP + GitMCP)")

            conversation = openai_client.conversations.create()

            question = "Show me how to create a hosted agent in Microsoft Foundry. Include both the concept explanation and a code example."
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": question}],
            )
            print(f"\n[Q] {question}")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            response = handle_mcp_approval(response, openai_client, conversation.id, agent.name)
            print(f"\n[A] {response.output_text}")

            # Resources kept for portal demo
            # openai_client.conversations.delete(conversation_id=conversation.id)
            # project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            print(f"\n📌 Resources preserved (agent: {agent.name})")


def main():
    print("=" * 60)
    print("DEMO 2d — Agents with MCP (Model Context Protocol) Tools")
    print("=" * 60)

    # Run all three parts
    demo_microsoft_learn_mcp()
    demo_gitmcp()
    demo_multiple_mcp()

    print("\n" + "=" * 60)
    print("✅ Demo 2d complete — all MCP examples executed")
    print("=" * 60)


if __name__ == "__main__":
    main()
