"""
Demo 2b — Agent with a custom Function Tool (on-the-fly tool definition)

This demo shows how to:
  1. Define a FunctionTool with a JSON schema for parameters
  2. Create an agent that can call that function
  3. Handle the function_call loop: detect call → execute → send result back
  4. The agent uses the function result to compose its final answer

This is the "on the go" pattern: tools are defined in YOUR code and the agent
invokes them when needed. The function runs locally — not in Azure.
"""

import os
import json
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-function-tool-agent"


# ── Define the local function that the agent can call ───────────
def get_weather(city: str, unit: str = "celsius") -> dict:
    """Simulate a weather API call. In production this would call a real API."""
    mock_data = {
        "Madrid": {"temp": 28, "condition": "Sunny", "humidity": 35},
        "London": {"temp": 14, "condition": "Cloudy", "humidity": 78},
        "Tokyo": {"temp": 22, "condition": "Partly cloudy", "humidity": 60},
        "New York": {"temp": 18, "condition": "Rainy", "humidity": 85},
    }
    weather = mock_data.get(city, {"temp": 20, "condition": "Unknown", "humidity": 50})
    if unit == "fahrenheit":
        weather["temp"] = round(weather["temp"] * 9 / 5 + 32)
    return {"city": city, "unit": unit, **weather}


# ── Define the FunctionTool schema ──────────────────────────────
weather_tool = FunctionTool(
    name="get_weather",
    description="Get the current weather for a given city.",
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "The city name, e.g. 'Madrid' or 'London'",
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit. Defaults to celsius.",
            },
        },
        "required": ["city"],
        "additionalProperties": False,
    },
    strict=True,
)


def handle_function_calls(response, openai_client, conversation_id, agent_name):
    """Process function_call items, execute the function, and send results back."""
    # Check if the response contains function calls
    function_calls = [item for item in response.output if item.type == "function_call"]
    if not function_calls:
        return response  # No function calls, return as-is

    # Execute each function call and collect results
    tool_outputs = []
    for call in function_calls:
        print(f"  🔧 Agent called: {call.name}({call.arguments})")
        args = json.loads(call.arguments)

        # Dispatch to the actual function
        if call.name == "get_weather":
            result = get_weather(**args)
        else:
            result = {"error": f"Unknown function: {call.name}"}

        tool_outputs.append({
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(result),
        })
        print(f"  📤 Result: {json.dumps(result)}")

    # Send the function results back to the agent
    response = openai_client.responses.create(
        conversation=conversation_id,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
        input=tool_outputs,
    )
    # Recurse in case the agent makes additional function calls
    return handle_function_calls(response, openai_client, conversation_id, agent_name)


def main():
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            print("=" * 60)
            print("DEMO 2b — Agent with Custom Function Tool")
            print("=" * 60)

            # ── Create agent with the function tool ─────────────────
            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a weather assistant. Use the get_weather tool to look up "
                        "current weather when users ask about weather conditions in a city. "
                        "Always provide the temperature and conditions in your response."
                    ),
                    tools=[weather_tool],
                ),
            )
            print(f"\n📌 Agent created with FunctionTool: name={agent.name}")

            # ── Create conversation and chat ────────────────────────
            conversation = openai_client.conversations.create()

            # Turn 1: Ask about weather (triggers function call)
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": "What's the weather like in Madrid right now?"}],
            )
            print(f"\n[Turn 1] Q: What's the weather like in Madrid right now?")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            response = handle_function_calls(response, openai_client, conversation.id, agent.name)
            print(f"[Turn 1] A: {response.output_text}")

            # Turn 2: Ask about another city
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": "How about London? Is it warmer or colder than Madrid?"}],
            )
            print(f"\n[Turn 2] Q: How about London? Is it warmer or colder than Madrid?")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )
            response = handle_function_calls(response, openai_client, conversation.id, agent.name)
            print(f"[Turn 2] A: {response.output_text}")

            # ── Resources kept for portal demo ─────────────────────
            # openai_client.conversations.delete(conversation_id=conversation.id)
            # project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            print(f"\n📌 Resources preserved (agent: {agent.name}, conversation: {conversation.id})")
            print(f"   View them in the Foundry portal.")

    print("\n✅ Demo 2b complete.")


if __name__ == "__main__":
    main()
