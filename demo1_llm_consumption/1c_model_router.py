"""
Demo 1c — Azure Model Router: Smart routing across multiple LLMs

Model Router is a single deployment that automatically selects the best
underlying LLM for each prompt in real-time. Different prompts may be
answered by different models (gpt-4.1-nano, gpt-5, DeepSeek, etc.)
depending on the routing mode (Balanced, Quality, Cost).

This demo sends multiple prompts of varying complexity and shows
detailed response metadata for each:
  - Which underlying model was selected by the router
  - Token usage (prompt, completion, reasoning, cached)
  - Response time (latency)
  - Finish reason

PREREQUISITE:
  Deploy "model-router" from the Foundry model catalog.
  Set MODEL_ROUTER_DEPLOYMENT_NAME in your .env file
  (defaults to "model-router" if not set).

  Routing modes (configured in portal, not in code):
    - Balanced (default): Optimizes cost while maintaining quality
    - Quality: For critical tasks (legal, medical, complex reasoning)
    - Cost: For high-volume, budget-sensitive workloads
"""

import os
import time
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL_ROUTER = os.environ.get("MODEL_ROUTER_DEPLOYMENT_NAME", "model-router")

# Model Router uses the Chat Completions API on the Azure OpenAI endpoint.
# We derive the AOAI endpoint from the Foundry project endpoint's resource name.
AZURE_OPENAI_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    "https://"
    + PROJECT_ENDPOINT.split("//")[1].split(".")[0]
    + ".openai.azure.com/",
)


def call_and_inspect(openai_client, messages, label):
    """Send a Chat Completions request and display detailed response metadata."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")

    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    print(f"  Prompt: {user_msg[:100]}{'...' if len(user_msg) > 100 else ''}")

    start_time = time.time()
    response = openai_client.chat.completions.create(
        model=MODEL_ROUTER,
        messages=messages,
    )
    elapsed = time.time() - start_time

    choice = response.choices[0]
    usage = response.usage

    # ── Response text ───────────────────────────────────────
    answer = choice.message.content or ""
    print(f"\n  Response: {answer[:200]}{'...' if len(answer) > 200 else ''}")

    # ── Model selected by the router ────────────────────────
    print(f"\n  ┌─────────────────────────────────────────────────────┐")
    print(f"  │ ROUTING & PERFORMANCE DETAILS                       │")
    print(f"  ├─────────────────────────────────────────────────────┤")
    print(f"  │ Model selected:    {response.model:<33}│")
    print(f"  │ Finish reason:     {choice.finish_reason:<33}│")
    print(f"  │ Response time:     {elapsed:.2f}s{'':<30}│")
    print(f"  │ Response ID:       {response.id[:33]:<33}│")
    print(f"  ├─────────────────────────────────────────────────────┤")
    print(f"  │ TOKEN USAGE                                         │")
    print(f"  ├─────────────────────────────────────────────────────┤")
    print(f"  │ Prompt tokens:     {usage.prompt_tokens:<33}│")
    print(f"  │ Completion tokens: {usage.completion_tokens:<33}│")
    print(f"  │ Total tokens:      {usage.total_tokens:<33}│")

    # Detailed token breakdown (if available)
    if usage.completion_tokens_details:
        ctd = usage.completion_tokens_details
        reasoning = getattr(ctd, "reasoning_tokens", 0) or 0
        if reasoning:
            print(f"  │ ↳ Reasoning:      {reasoning:<33}│")
        accepted_pred = getattr(ctd, "accepted_prediction_tokens", 0) or 0
        if accepted_pred:
            print(f"  │ ↳ Accepted pred:  {accepted_pred:<33}│")

    if usage.prompt_tokens_details:
        ptd = usage.prompt_tokens_details
        cached = getattr(ptd, "cached_tokens", 0) or 0
        if cached:
            print(f"  │ Cached tokens:    {cached:<33}│")

    print(f"  └─────────────────────────────────────────────────────┘")

    return response.model


def main():
    print("=" * 60)
    print("DEMO 1c — Azure Model Router")
    print(f"Deployment: {MODEL_ROUTER}")
    print(f"Endpoint:   {AZURE_OPENAI_ENDPOINT}")
    print("=" * 60)
    print("\nSending prompts of varying complexity to see how the router")
    print("selects different underlying models for each request.\n")

    # Model Router uses Chat Completions API with the Azure OpenAI endpoint
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    openai_client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-04-01-preview",
    )

    models_used = []

    # ── Prompt 1: Simple factual question ───────────────────
    model = call_and_inspect(openai_client, [
        {"role": "system", "content": "You are a helpful assistant. Be concise."},
        {"role": "user", "content": "What is the capital of Japan?"},
    ], "PROMPT 1 — Simple factual (likely routed to a smaller model)")
    models_used.append(("Simple factual", model))

    # ── Prompt 2: Classification task ───────────────────────
    model = call_and_inspect(openai_client, [
        {"role": "system", "content": "Classify the sentiment as positive, negative, or neutral. Reply with just the label."},
        {"role": "user", "content": "I absolutely loved the new restaurant downtown, the food was amazing and the service was impeccable!"},
    ], "PROMPT 2 — Quick classification (likely a fast/cheap model)")
    models_used.append(("Classification", model))

    # ── Prompt 3: Creative writing ──────────────────────────
    model = call_and_inspect(openai_client, [
        {"role": "system", "content": "You are a creative writer."},
        {"role": "user", "content": "Write a short story (100 words) about a robot discovering music for the first time."},
    ], "PROMPT 3 — Creative writing (may use a mid-tier model)")
    models_used.append(("Creative writing", model))

    # ── Prompt 4: Complex reasoning ─────────────────────────
    model = call_and_inspect(openai_client, [
        {"role": "system", "content": "You are an expert mathematician. Show your work step by step."},
        {"role": "user", "content": (
            "A train leaves Madrid at 9:00 AM traveling at 120 km/h. "
            "Another train leaves Barcelona (620 km away) at 9:30 AM traveling at 150 km/h toward Madrid. "
            "At what time do they meet, and how far from Madrid?"
        )},
    ], "PROMPT 4 — Complex reasoning (likely a larger/reasoning model)")
    models_used.append(("Complex reasoning", model))

    # ── Prompt 5: Code generation ───────────────────────────
    model = call_and_inspect(openai_client, [
        {"role": "system", "content": "You are an expert Python developer. Write clean, production-quality code."},
        {"role": "user", "content": (
            "Write a Python function that implements a thread-safe LRU cache "
            "with a configurable max size, TTL expiry, and hit/miss statistics. "
            "Include type hints and docstrings."
        )},
    ], "PROMPT 5 — Code generation (likely a capable code model)")
    models_used.append(("Code generation", model))

    # ── Prompt 6: Simple translation ────────────────────────
    model = call_and_inspect(openai_client, [
        {"role": "user", "content": "Translate to French: 'The weather is nice today.'"},
    ], "PROMPT 6 — Simple translation (likely a small/fast model)")
    models_used.append(("Translation", model))

    # ── Summary: Which models were selected ─────────────────
    print("\n" + "=" * 60)
    print("📊 ROUTING SUMMARY")
    print("=" * 60)
    print(f"\n  {'Prompt Type':<25} {'Model Selected'}")
    print(f"  {'─' * 25} {'─' * 35}")
    for prompt_type, model in models_used:
        print(f"  {prompt_type:<25} {model}")

    unique_models = set(m for _, m in models_used)
    print(f"\n  Unique models used: {len(unique_models)} out of {len(models_used)} prompts")
    for m in sorted(unique_models):
        print(f"    • {m}")

    print("\n✅ Demo 1c complete.")


if __name__ == "__main__":
    main()
