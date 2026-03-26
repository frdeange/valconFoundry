"""
Demo 2a — Create a basic Foundry Agent and have a multi-turn conversation

This demo shows the full agent lifecycle with SDK v2:
  1. Create an agent version (PromptAgentDefinition)
  2. Create a conversation
  3. Send messages and get responses via agent_reference
  4. Multi-turn with conversation context
  5. Clean up (delete conversation + agent version)
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-basic-agent"


def main():
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            # ── Step 1: Create the agent ────────────────────────────
            print("=" * 60)
            print("DEMO 2a — Basic Agent with Multi-turn Conversation")
            print("=" * 60)

            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a travel assistant specialized in European destinations. "
                        "Provide concise, practical travel advice."
                    ),
                ),
            )
            print(f"\n📌 Agent created: name={agent.name}, id={agent.id}, version={agent.version}")

            # ── Step 2: Create a conversation ───────────────────────
            conversation = openai_client.conversations.create()
            print(f"💬 Conversation created: id={conversation.id}")

            # ── Step 3: First turn ──────────────────────────────────
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": "I want to visit Portugal. What are the top 3 cities to visit?"}],
            )

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            print(f"\n[Turn 1] Q: I want to visit Portugal. What are the top 3 cities to visit?")
            print(f"[Turn 1] A: {response.output_text}")

            # ── Step 4: Second turn (agent remembers context) ───────
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": "What is the best time of year to go to the first city you mentioned?"}],
            )

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            print(f"\n[Turn 2] Q: What is the best time of year to go to the first city you mentioned?")
            print(f"[Turn 2] A: {response.output_text}")

            # ── Step 5: Third turn ──────────────────────────────────
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": "Recommend a local dish I must try there."}],
            )

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            print(f"\n[Turn 3] Q: Recommend a local dish I must try there.")
            print(f"[Turn 3] A: {response.output_text}")

            # ── Step 6: Resources kept for portal demo ─────────────
            # openai_client.conversations.delete(conversation_id=conversation.id)
            # project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            print(f"\n📌 Resources preserved (agent: {agent.name}, conversation: {conversation.id})")
            print(f"   View them in the Foundry portal.")

    print("\n✅ Demo 2a complete.")


if __name__ == "__main__":
    main()
