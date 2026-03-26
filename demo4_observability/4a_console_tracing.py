"""
Demo 4a — Observability: Agent tracing to the console (OpenTelemetry)

This demo shows how to enable tracing so you can see every LLM call,
tool invocation, and agent step printed to the terminal. Great for
debugging and understanding what happens "under the hood".

Key concepts:
  - AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true must be set BEFORE instrumenting
  - AIProjectInstrumentor().instrument() patches the SDK to emit spans
  - ConsoleSpanExporter prints spans to stdout
  - @trace_function decorator traces your own custom functions
"""

import os

# IMPORTANT: Must be set before importing the instrumentor
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from azure.ai.projects.telemetry import AIProjectInstrumentor, trace_function
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-traced-agent"

# ── Setup OpenTelemetry: Console exporter ───────────────────────
span_exporter = ConsoleSpanExporter()
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# ── Instrument the Foundry SDK ──────────────────────────────────
AIProjectInstrumentor().instrument()


# ── Custom function decorated with @trace_function ──────────────
@trace_function("lookup_population")
def lookup_population(country: str) -> str:
    """Look up population data — traced automatically via @trace_function."""
    populations = {
        "Spain": "47.4 million",
        "France": "68.0 million",
        "Germany": "84.5 million",
        "Italy": "58.9 million",
    }
    return populations.get(country, f"Population data not available for {country}")


population_tool = FunctionTool(
    name="lookup_population",
    description="Look up the population of a European country.",
    parameters={
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "Country name, e.g. 'Spain'"},
        },
        "required": ["country"],
        "additionalProperties": False,
    },
    strict=True,
)


def main():
    import json

    print("=" * 60)
    print("DEMO 4a — Console Tracing (OpenTelemetry)")
    print("=" * 60)
    print("\n📊 Traces will appear below between the conversation output.\n")

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            # Wrap the entire scenario in a trace span
            with tracer.start_as_current_span("demo4a_console_tracing"):

                agent = project_client.agents.create_version(
                    agent_name=AGENT_NAME,
                    definition=PromptAgentDefinition(
                        model=MODEL,
                        instructions="You are a geography expert. Use the lookup_population tool when asked about population.",
                        tools=[population_tool],
                    ),
                )
                print(f"📌 Agent created: {agent.name}")

                conversation = openai_client.conversations.create()

                openai_client.conversations.items.create(
                    conversation_id=conversation.id,
                    items=[{"type": "message", "role": "user", "content": "What is the population of Spain?"}],
                )

                response = openai_client.responses.create(
                    conversation=conversation.id,
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                )

                # Handle function calls
                function_calls = [item for item in response.output if item.type == "function_call"]
                if function_calls:
                    tool_outputs = []
                    for call in function_calls:
                        args = json.loads(call.arguments)
                        result = lookup_population(**args)
                        tool_outputs.append({
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": result,
                        })

                    response = openai_client.responses.create(
                        conversation=conversation.id,
                        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                        input=tool_outputs,
                    )

                print(f"\n💬 Agent response: {response.output_text}")

                # Cleanup
                openai_client.conversations.delete(conversation_id=conversation.id)

            project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)

    print("\n✅ Demo 4a complete. Review the trace spans printed above.")


if __name__ == "__main__":
    main()
