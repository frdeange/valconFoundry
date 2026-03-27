"""
Demo 2f — Create an agent from a YAML definition file

This demo shows the "agent-as-code" pattern: define your agent declaratively
in a YAML file (instructions, model, tools) and create it programmatically.

Benefits of this approach:
  - Version-control agent definitions in Git (review changes in PRs)
  - Separate agent config from application logic
  - Deploy different configs per environment (dev/staging/prod)
  - Non-developers can edit the YAML without touching Python code

The YAML file (agent_definitions/travel_assistant.yaml) defines:
  - Agent name and instructions
  - Model (with ${MODEL} variable resolved at runtime)
  - Function tools with full JSON Schema definitions
  - Test queries for quick validation

This pattern complements the Foundry portal manifest approach — you can
maintain your agent definitions in code while still managing them in the portal.
"""

import os
import json
import yaml
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]

YAML_PATH = os.path.join(os.path.dirname(__file__), "agent_definitions", "travel_assistant.yaml")


# ── Mock functions for the tools defined in YAML ────────────────
def get_flight_price(origin: str, destination: str, travel_class: str) -> dict:
    """Mock flight price lookup."""
    prices = {
        "economy": {"base": 80, "per_km": 0.05},
        "business": {"base": 250, "per_km": 0.15},
        "first": {"base": 500, "per_km": 0.30},
    }
    import random
    base = prices.get(travel_class, prices["economy"])
    price = base["base"] + random.randint(50, 200)
    return {
        "origin": origin,
        "destination": destination,
        "class": travel_class,
        "estimated_price_eur": price,
        "currency": "EUR",
        "note": "Approximate price. Book early for better deals.",
    }


def get_hotel_recommendation(city: str, budget_per_night: str, nights: int) -> dict:
    """Mock hotel recommendation."""
    hotels = {
        "budget": {"name": "City Hostel", "price_per_night": 45, "rating": 3.8},
        "mid-range": {"name": "Grand Hotel Central", "price_per_night": 120, "rating": 4.3},
        "luxury": {"name": "The Palace Resort", "price_per_night": 350, "rating": 4.9},
    }
    hotel = hotels.get(budget_per_night, hotels["mid-range"])
    return {
        "city": city,
        "hotel": hotel["name"],
        "price_per_night_eur": hotel["price_per_night"],
        "total_eur": hotel["price_per_night"] * nights,
        "nights": nights,
        "rating": hotel["rating"],
    }


FUNCTION_DISPATCH = {
    "get_flight_price": get_flight_price,
    "get_hotel_recommendation": get_hotel_recommendation,
}


def load_agent_definition(yaml_path: str) -> dict:
    """Load and resolve an agent definition from a YAML file."""
    with open(yaml_path, "r") as f:
        definition = yaml.safe_load(f)

    # Resolve ${MODEL} variable
    if definition.get("model") == "${MODEL}":
        definition["model"] = MODEL

    return definition


def create_tools_from_yaml(tool_defs: list) -> list:
    """Convert YAML tool definitions to SDK FunctionTool objects."""
    tools = []
    for t in tool_defs:
        if t["type"] == "function":
            tools.append(FunctionTool(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"],
                strict=t.get("strict", False),
            ))
    return tools


def handle_function_calls(response, openai_client, agent_name):
    """Process function_call items, execute the function, and send results back."""
    function_calls = [item for item in response.output if item.type == "function_call"]
    if not function_calls:
        return response

    tool_outputs = []
    for call in function_calls:
        print(f"  🔧 Tool call: {call.name}({call.arguments})")
        args = json.loads(call.arguments)
        func = FUNCTION_DISPATCH.get(call.name)
        if func:
            result = func(**args)
        else:
            result = {"error": f"Unknown function: {call.name}"}
        tool_outputs.append({
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(result),
        })
        print(f"  📤 Result: {json.dumps(result, indent=2)}")

    response = openai_client.responses.create(
        input=tool_outputs,
        previous_response_id=response.id,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
    )
    return handle_function_calls(response, openai_client, agent_name)


def main():
    print("=" * 60)
    print("DEMO 2f — Agent from YAML Definition")
    print("=" * 60)

    # ── Step 1: Load the YAML definition ────────────────────────
    print(f"\n📄 Loading agent definition from: {YAML_PATH}")
    definition = load_agent_definition(YAML_PATH)

    print(f"   Name:         {definition['name']}")
    print(f"   Model:        {definition['model']}")
    print(f"   Tools:        {len(definition.get('tools', []))}")
    print(f"   Instructions: {definition['instructions'][:80]}...")

    # ── Step 2: Create the agent from the YAML definition ───────
    tools = create_tools_from_yaml(definition.get("tools", []))

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            agent = project_client.agents.create_version(
                agent_name=definition["name"],
                definition=PromptAgentDefinition(
                    model=definition["model"],
                    instructions=definition["instructions"],
                    tools=tools,
                ),
            )
            print(f"\n📌 Agent created from YAML: {agent.name} (version {agent.version})")

            # ── Step 3: Run test queries from the YAML ──────────
            test_queries = definition.get("test_queries", [])
            print(f"\n🧪 Running {len(test_queries)} test queries from YAML...")

            for i, query in enumerate(test_queries, 1):
                print(f"\n{'─' * 50}")
                print(f"[Q{i}] {query}")

                response = openai_client.responses.create(
                    input=[{"role": "user", "content": query}],
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                )
                response = handle_function_calls(response, openai_client, agent.name)
                print(f"\n[A{i}] {response.output_text}")

            print(f"\n📌 Resources preserved (agent: {agent.name})")

    print("\n✅ Demo 2f complete.")


if __name__ == "__main__":
    main()
