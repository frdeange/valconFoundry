"""
Hosted Agent — Agent application code using Microsoft Agent Framework

This file defines the agent logic that will run inside a container.
The hosting adapter (azure-ai-agentserver-agentframework) wraps it as an
HTTP service compatible with the Foundry Responses API.

To test locally:
  1. pip install -r requirements_hosted.txt
  2. Set AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME in your .env
  3. python agent_app.py
  4. Test: curl -X POST http://localhost:8088/responses \
       -H "Content-Type: application/json" \
       -d '{"input": "What time is it in Tokyo?"}'
"""

import asyncio
import os
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(override=True)

from agent_framework import Agent
from agent_framework.azure import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential

PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")


def get_local_date_time(
    iana_timezone: Annotated[str, "The IANA timezone string (e.g. 'Europe/Madrid', 'America/New_York')"],
) -> str:
    """
    Get the current date and time for a given timezone.

    This is a LOCAL Python function that runs on the server — demonstrating
    how code-based agents can execute custom logic that prompt agents cannot.
    """
    try:
        tz = ZoneInfo(iana_timezone)
        current_time = datetime.now(tz)
        return (
            f"The current date and time in {iana_timezone} is "
            f"{current_time.strftime('%A, %B %d, %Y at %I:%M %p %Z')}"
        )
    except Exception as e:
        return f"Error: Unable to get time for timezone '{iana_timezone}'. {str(e)}"


def convert_currency(
    amount: Annotated[float, "The amount to convert"],
    from_currency: Annotated[str, "Source currency code (e.g. 'USD', 'EUR')"],
    to_currency: Annotated[str, "Target currency code (e.g. 'EUR', 'GBP')"],
) -> str:
    """Convert an amount from one currency to another (mock rates for demo)."""
    mock_rates = {
        ("USD", "EUR"): 0.92, ("EUR", "USD"): 1.09,
        ("USD", "GBP"): 0.79, ("GBP", "USD"): 1.27,
        ("EUR", "GBP"): 0.86, ("GBP", "EUR"): 1.16,
    }
    rate = mock_rates.get((from_currency.upper(), to_currency.upper()))
    if rate is None:
        return f"Conversion from {from_currency} to {to_currency} is not available."
    converted = round(amount * rate, 2)
    return f"{amount} {from_currency} = {converted} {to_currency} (rate: {rate})"


async def main():
    async with (
        DefaultAzureCredential() as credential,
        AzureAIAgentClient(
            project_endpoint=PROJECT_ENDPOINT,
            model_deployment_name=MODEL_DEPLOYMENT_NAME,
            credential=credential,
        ) as client,
    ):
        agent = Agent(
            client,
            name="demo-travel-assistant",
            instructions=(
                "You are a helpful travel assistant that can tell users the current "
                "date and time in any location and convert currencies for trip planning. "
                "Use the get_local_date_time tool for time queries and convert_currency "
                "for currency questions."
            ),
            tools=[get_local_date_time, convert_currency],
        )

        print("Travel Assistant Agent Server running on http://localhost:8088")
        server = from_agent_framework(agent)
        await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
