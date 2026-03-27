"""
Demo 2g — Agent with Structured Output (JSON Schema)

This demo shows how to create an agent that returns responses in a strict
JSON format defined by a schema. The agent ALWAYS returns valid JSON matching
the schema — never free-form text.

Scenario: A "Lead Qualifier" agent that analyzes a sales inquiry and returns
structured data for a CRM system: contact info, company, interest level,
recommended action, and follow-up date.

Key concepts:
  - PromptAgentDefinitionTextOptions with TextResponseFormatJsonSchema
  - Pydantic model defines the schema (auto-generates JSON Schema)
  - The response is always valid JSON matching the schema
  - Use json.loads() to parse and work with the structured data

Use cases for structured output:
  - CRM lead qualification (this demo)
  - Invoice/receipt extraction
  - Ticket classification and routing
  - Data extraction from unstructured text
  - API response formatting
"""

import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    PromptAgentDefinitionTextOptions,
    TextResponseFormatJsonSchema,
)

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-structured-output-agent"


# ── Define the output schema with Pydantic ──────────────────────
# Pydantic models auto-generate JSON Schema that the agent must follow.
# The model_config = {"extra": "forbid"} ensures additionalProperties: false.

class ContactInfo(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(description="Full name of the contact person")
    email: str = Field(description="Email address")
    phone: str = Field(description="Phone number, or 'N/A' if not provided")
    role: str = Field(description="Job title or role in the company")


class LeadQualification(BaseModel):
    model_config = {"extra": "forbid"}
    contact: ContactInfo = Field(description="Contact information extracted from the inquiry")
    company: str = Field(description="Company name")
    industry: str = Field(description="Industry sector (e.g. 'Technology', 'Healthcare', 'Finance')")
    interest: str = Field(description="What product/service they are interested in")
    interest_level: str = Field(description="One of: 'hot', 'warm', 'cold'")
    budget_mentioned: bool = Field(description="Whether a budget was mentioned")
    budget_range: str = Field(description="Budget range if mentioned, or 'Not specified'")
    recommended_action: str = Field(description="Recommended next action for the sales team")
    follow_up_date: str = Field(description="Suggested follow-up date in YYYY-MM-DD format")
    summary: str = Field(description="One-sentence summary of the lead")


def resolve_schema_refs(schema: dict) -> dict:
    """Inline all $ref/$defs in a JSON Schema so it's compatible with structured outputs.
    OpenAI structured outputs don't allow $ref with sibling keywords like 'description'."""
    defs = schema.pop("$defs", {})

    def resolve(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_name = obj["$ref"].split("/")[-1]
                resolved = defs.get(ref_name, {}).copy()
                # Merge any sibling keys (e.g. description) into the resolved object
                for k, v in obj.items():
                    if k != "$ref":
                        resolved[k] = v
                return resolve(resolved)
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(item) for item in obj]
        return obj

    return resolve(schema)


def main():
    print("=" * 60)
    print("DEMO 2g — Agent with Structured Output (JSON Schema)")
    print("=" * 60)

    # Generate schema from Pydantic and resolve $refs for OpenAI compatibility
    raw_schema = LeadQualification.model_json_schema()
    schema = resolve_schema_refs(raw_schema)
    print(f"\n📋 JSON Schema the agent must follow:")
    print(json.dumps(schema, indent=2)[:500] + "...\n")

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            # Create agent with structured output
            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a sales lead qualification assistant. "
                        "Analyze incoming sales inquiries and extract structured information. "
                        "For interest_level, use: 'hot' (ready to buy), 'warm' (interested but exploring), "
                        "'cold' (just browsing or unlikely to convert). "
                        "For follow_up_date, suggest a date based on urgency: "
                        "hot leads within 1-2 days, warm within a week, cold within 2 weeks. "
                        "Today's date is 2026-03-27."
                    ),
                    text=PromptAgentDefinitionTextOptions(
                        format=TextResponseFormatJsonSchema(
                            name="LeadQualification",
                            schema=schema,
                        )
                    ),
                ),
            )
            print(f"📌 Agent created: {agent.name} (with structured output)")

            # ── Test with different sales inquiry scenarios ──────

            inquiries = [
                # Hot lead — urgent, budget mentioned
                {
                    "label": "Hot Lead (urgent, budget mentioned)",
                    "text": (
                        "Hi, I'm Maria Garcia, CTO at CloudScale Solutions (maria@cloudscale.io, +34 612 345 678). "
                        "We're a fintech company looking to implement AI-powered customer service automation ASAP. "
                        "We have a budget of 150K-200K EUR approved for Q2. "
                        "Can we schedule a demo this week?"
                    ),
                },
                # Warm lead — interested but exploring
                {
                    "label": "Warm Lead (exploring options)",
                    "text": (
                        "Hello, my name is James Wilson from HealthFirst Inc. I'm the VP of Operations. "
                        "We're a healthcare company evaluating different AI platforms for internal process automation. "
                        "We're still in the research phase and would like to understand your pricing model. "
                        "You can reach me at jwilson@healthfirst.com."
                    ),
                },
                # Cold lead — vague inquiry
                {
                    "label": "Cold Lead (vague inquiry)",
                    "text": (
                        "Hey, saw your product on LinkedIn. Looks interesting. "
                        "I work at a small retail startup. Just curious about what you offer. "
                        "— Tom B. (tom@quickshop.co)"
                    ),
                },
            ]

            for i, inquiry in enumerate(inquiries, 1):
                print(f"\n{'═' * 50}")
                print(f"  Inquiry {i}: {inquiry['label']}")
                print(f"{'═' * 50}")
                print(f"  Input: {inquiry['text'][:100]}...")

                response = openai_client.responses.create(
                    input=[{"role": "user", "content": inquiry["text"]}],
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                )

                # Parse the structured JSON response
                try:
                    data = json.loads(response.output_text)
                    lead = LeadQualification.model_validate(data)

                    print(f"\n  📊 Structured Output:")
                    print(f"     Contact:     {lead.contact.name} ({lead.contact.role})")
                    print(f"     Company:     {lead.company} [{lead.industry}]")
                    print(f"     Email:       {lead.contact.email}")
                    print(f"     Interest:    {lead.interest}")
                    print(f"     Level:       {'🔥' if lead.interest_level == 'hot' else '🟡' if lead.interest_level == 'warm' else '🔵'} {lead.interest_level.upper()}")
                    print(f"     Budget:      {'✅' if lead.budget_mentioned else '❌'} {lead.budget_range}")
                    print(f"     Action:      {lead.recommended_action}")
                    print(f"     Follow-up:   {lead.follow_up_date}")
                    print(f"     Summary:     {lead.summary}")
                except json.JSONDecodeError as e:
                    print(f"\n  ❌ Response was not valid JSON: {e}")
                    print(f"     Raw: {response.output_text[:200]}")
                except Exception as e:
                    print(f"\n  ❌ Schema validation failed: {e}")
                    print(f"     Raw: {response.output_text[:200]}")

            print(f"\n📌 Resources preserved (agent: {agent.name})")

    print("\n✅ Demo 2g complete.")


if __name__ == "__main__":
    main()
