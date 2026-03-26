"""
Demo 1a — Consume an LLM via the Microsoft Foundry SDK (Responses API)

This demo shows how to call an LLM through the Foundry project client,
which handles authentication, endpoint routing, and provides access to
the OpenAI Responses API — the recommended approach for Foundry projects.

Key points shown:
  - AIProjectClient creates an authenticated OpenAI client automatically
  - The Responses API (openai_client.responses.create) is the new standard
  - Multi-turn is handled via previous_response_id (no manual history)
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]


def main():
    # 1. Create the Foundry project client (handles auth + endpoint)
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        # 2. Get an authenticated OpenAI client — no manual keys or endpoints needed
        with project_client.get_openai_client() as openai_client:

            # 3. Single-turn call using the Responses API
            print("=" * 60)
            print("FOUNDRY SDK — Responses API")
            print("=" * 60)

            response = openai_client.responses.create(
                model=MODEL,
                input="What is the population of Spain?",
            )
            print(f"\n[Turn 1] Q: What is the population of Spain?")
            print(f"[Turn 1] A: {response.output_text}")

            # 4. Multi-turn: use previous_response_id to keep context
            response = openai_client.responses.create(
                model=MODEL,
                input="And what is its capital city?",
                previous_response_id=response.id,
            )
            print(f"\n[Turn 2] Q: And what is its capital city?")
            print(f"[Turn 2] A: {response.output_text}")

            # 5. One more follow-up
            response = openai_client.responses.create(
                model=MODEL,
                input="Tell me three famous landmarks there.",
                previous_response_id=response.id,
            )
            print(f"\n[Turn 3] Q: Tell me three famous landmarks there.")
            print(f"[Turn 3] A: {response.output_text}")

    print("\n✅ Demo 1a complete.")


if __name__ == "__main__":
    main()
