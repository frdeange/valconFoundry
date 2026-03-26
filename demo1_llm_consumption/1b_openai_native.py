"""
Demo 1b — Consume an LLM via the vanilla OpenAI SDK (Azure OpenAI endpoint)

This demo shows the "traditional" way to call Azure OpenAI directly,
WITHOUT the Foundry project layer. This is useful to compare approaches.

Key differences vs. Demo 1a (Foundry SDK):
  ┌──────────────────────────┬──────────────────────────────────────┐
  │  Foundry SDK (1a)        │  Direct OpenAI SDK (1b)              │
  ├──────────────────────────┼──────────────────────────────────────┤
  │  AIProjectClient handles │  You manually build AzureOpenAI      │
  │  endpoint + auth         │  with endpoint + token provider      │
  ├──────────────────────────┼──────────────────────────────────────┤
  │  Responses API           │  Chat Completions API                │
  │  (responses.create)      │  (chat.completions.create)           │
  ├──────────────────────────┼──────────────────────────────────────┤
  │  Multi-turn via          │  Multi-turn via manual messages list │
  │  previous_response_id    │  (you manage the history)            │
  ├──────────────────────────┼──────────────────────────────────────┤
  │  Project-aware: tracing, │  Model-only: no project context,     │
  │  agents, eval, datasets  │  no built-in Foundry features        │
  └──────────────────────────┴──────────────────────────────────────┘
"""

import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

load_dotenv()

# You need the Azure OpenAI endpoint (NOT the Foundry project endpoint).
# Typically: https://<your-resource>.openai.azure.com/
# For simplicity, we derive it from the Foundry project endpoint's resource.
AZURE_OPENAI_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    # Fallback: extract resource name from Foundry endpoint and build AOAI URL
    "https://"
    + os.environ["AZURE_AI_PROJECT_ENDPOINT"].split("//")[1].split(".")[0]
    + ".openai.azure.com/",
)
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]


def main():
    # 1. Set up Entra ID token provider (no API keys needed)
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    # 2. Create the AzureOpenAI client manually
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-03-01-preview",
    )

    print("=" * 60)
    print("DIRECT OPENAI SDK — Chat Completions API")
    print("=" * 60)

    # 3. Single-turn call using Chat Completions API
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the population of Spain?"},
    ]

    response = client.chat.completions.create(model=MODEL, messages=messages)
    answer = response.choices[0].message.content
    print(f"\n[Turn 1] Q: What is the population of Spain?")
    print(f"[Turn 1] A: {answer}")

    # 4. Multi-turn: you MUST manually append messages to the history
    messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": "And what is its capital city?"})

    response = client.chat.completions.create(model=MODEL, messages=messages)
    answer = response.choices[0].message.content
    print(f"\n[Turn 2] Q: And what is its capital city?")
    print(f"[Turn 2] A: {answer}")

    # 5. One more follow-up
    messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": "Tell me three famous landmarks there."})

    response = client.chat.completions.create(model=MODEL, messages=messages)
    answer = response.choices[0].message.content
    print(f"\n[Turn 3] Q: Tell me three famous landmarks there.")
    print(f"[Turn 3] A: {answer}")

    print("\n✅ Demo 1b complete.")


if __name__ == "__main__":
    main()
