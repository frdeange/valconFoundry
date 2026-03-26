"""
Demo 4b — Observability: Agent tracing to Azure Monitor (Application Insights)

This demo sends all traces to Application Insights so you can view them
in the Microsoft Foundry portal (Tracing tab) or in Azure Monitor.

Prerequisites:
  - An Application Insights resource connected to your Foundry project
    (see the Tracing tab in Foundry portal)
  - APPLICATIONINSIGHTS_CONNECTION_STRING in your .env (optional —
    the script can also retrieve it automatically from the project)

Key concepts:
  - configure_azure_monitor() sets up the Azure Monitor exporter
  - project_client.telemetry.get_application_insights_connection_string()
    retrieves the connection string from your Foundry project
  - Traces appear in the Foundry portal under the Tracing tab
"""

import os

# IMPORTANT: Must be set before importing the instrumentor
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.ai.projects.telemetry import AIProjectInstrumentor
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-monitored-agent"


def main():
    print("=" * 60)
    print("DEMO 4b — Azure Monitor Tracing (Application Insights)")
    print("=" * 60)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        # ── Step 1: Get App Insights connection string ──────────────
        # Try from env first, then from the project
        conn_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if not conn_string:
            print("\n🔍 Retrieving App Insights connection string from project...")
            conn_string = project_client.telemetry.get_application_insights_connection_string()

        if not conn_string:
            print("⚠️  No Application Insights connected to this project.")
            print("   Connect one in the Foundry portal (Tracing tab) and retry.")
            return

        # ── Step 2: Configure Azure Monitor exporter ────────────────
        configure_azure_monitor(connection_string=conn_string)
        print(f"📡 Azure Monitor configured.")

        # ── Step 3: Instrument the SDK ──────────────────────────────
        AIProjectInstrumentor().instrument()

        tracer = trace.get_tracer(__name__)
        scenario = os.path.basename(__file__)

        with project_client.get_openai_client() as openai_client:

            # Wrap the entire demo in a span for easy identification
            with tracer.start_as_current_span(scenario):

                # ── Step 4: Create agent and chat ───────────────────
                agent = project_client.agents.create_version(
                    agent_name=AGENT_NAME,
                    definition=PromptAgentDefinition(
                        model=MODEL,
                        instructions="You are a friendly assistant. Answer questions concisely.",
                    ),
                )
                print(f"\n📌 Agent created: {agent.name}")

                conversation = openai_client.conversations.create()

                # Turn 1
                openai_client.conversations.items.create(
                    conversation_id=conversation.id,
                    items=[{"type": "message", "role": "user", "content": "What are the three tallest mountains in the world?"}],
                )
                response = openai_client.responses.create(
                    conversation=conversation.id,
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                )
                print(f"\n[Turn 1] A: {response.output_text}")

                # Turn 2
                openai_client.conversations.items.create(
                    conversation_id=conversation.id,
                    items=[{"type": "message", "role": "user", "content": "Which countries are they located in?"}],
                )
                response = openai_client.responses.create(
                    conversation=conversation.id,
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                )
                print(f"[Turn 2] A: {response.output_text}")

                # Cleanup
                openai_client.conversations.delete(conversation_id=conversation.id)

            project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)

    print(f"\n📊 Traces sent to Application Insights.")
    print(f"   View them in the Foundry portal → Tracing tab")
    print(f"   (traces may take 2-5 minutes to appear)")
    print("\n✅ Demo 4b complete.")


if __name__ == "__main__":
    main()
