"""
Demo 5c — Custom Evaluators: Create and use your own evaluation criteria

This demo shows how to create BOTH types of custom evaluators and run them
alongside built-in evaluators in a single evaluation:

  1. CODE-BASED evaluator — A Python grade() function that runs deterministic
     checks. No LLM involved. Good for:
       - Response length validation
       - Format checks (JSON, URLs, citations)
       - Keyword/regex matching
       - Any rule-based scoring

  2. PROMPT-BASED evaluator — A judge prompt evaluated by an LLM. Good for:
       - Subjective quality (friendliness, professionalism, brand tone)
       - Domain-specific accuracy
       - Semantic checks that need reasoning

  The flow:
    a) Register custom evaluators in the project's evaluator catalog
    b) Use them in testing_criteria just like built-in evaluators
    c) Combine custom + built-in evaluators in one evaluation run
    d) View results in the Foundry portal evaluator catalog

CUSTOM EVALUATOR TYPES:
  ┌────────────────────────────────────────────────────────────────────────┐
  │ CODE-BASED                        │ PROMPT-BASED                      │
  ├───────────────────────────────────┼───────────────────────────────────┤
  │ Python grade(sample, item) → float│ Judge prompt → LLM → JSON result │
  │ Returns 0.0 to 1.0               │ Returns {result, reason}          │
  │ Deterministic, fast, no LLM cost │ Subjective, uses LLM tokens       │
  │ Scoring: continuous only          │ Scoring: ordinal, continuous,     │
  │                                   │ or binary                         │
  │ Runs in sandboxed Python env     │ Runs via deployed model           │
  │ No network access                │ Needs deployment_name + threshold │
  └───────────────────────────────────┴───────────────────────────────────┘
"""

import os
import time
from pprint import pprint
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import EvaluatorCategory, EvaluatorDefinitionType
from openai.types.eval_create_params import DataSourceConfigCustom
from openai.types.evals.create_eval_jsonl_run_data_source_param import (
    CreateEvalJSONLRunDataSourceParam,
    SourceFileContent,
    SourceFileContentContent,
)

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]


# ═══════════════════════════════════════════════════════════════════
# STEP 1: Define the custom evaluator logic
# ═══════════════════════════════════════════════════════════════════

# ── Code-based evaluator: Response Quality Checker ──────────────
# Checks multiple quality rules with deterministic Python logic.
# Score 0.0-1.0 based on how many checks pass.
CODE_EVALUATOR_NAME = "response_quality_checker"
CODE_EVALUATOR_SOURCE = '''
def grade(sample: dict, item: dict) -> float:
    """
    Deterministic quality checker for LLM responses.
    Checks: length, sentence structure, no repetition, contains substance.
    Returns 0.0-1.0 based on proportion of checks passed.
    """
    import re

    # For model/agent target evaluation, response is in item["sample"]["output_text"]
    # For dataset evaluation, response is in item["response"]
    response = item.get("response", "")
    if not response:
        response = item.get("sample", {}).get("output_text", "")
    if not response:
        return 0.0

    checks_passed = 0
    total_checks = 5

    # Check 1: Minimum length (at least 20 characters)
    if len(response) >= 20:
        checks_passed += 1

    # Check 2: Maximum length (not excessively long, under 2000 chars)
    if len(response) <= 2000:
        checks_passed += 1

    # Check 3: Contains at least 2 sentences (has period/exclamation/question mark)
    sentence_endings = len(re.findall(r'[.!?]', response))
    if sentence_endings >= 2:
        checks_passed += 1

    # Check 4: No excessive repetition (same word 5+ times in a row)
    if not re.search(r'\\b(\\w+)\\b(?:\\s+\\1\\b){4,}', response):
        checks_passed += 1

    # Check 5: Starts with a capital letter or number (proper formatting)
    if re.match(r'^[A-Z0-9]', response.strip()):
        checks_passed += 1

    return checks_passed / total_checks
'''

# ── Prompt-based evaluator: Professionalism Scorer ──────────────
# Uses an LLM judge to rate the professionalism of a response.
PROMPT_EVALUATOR_NAME = "professionalism_scorer"
PROMPT_EVALUATOR_TEXT = """You are an expert evaluator assessing the professionalism of AI-generated responses.

Rate the professionalism of the following response on a scale of 1 to 5:

1 - Very unprofessional: Casual slang, errors, inappropriate tone
2 - Somewhat unprofessional: Mostly informal, occasional issues
3 - Neutral: Acceptable but not notably professional
4 - Professional: Clear, well-structured, appropriate tone
5 - Very professional: Excellent clarity, formal yet approachable, well-organized

Consider these criteria:
- Appropriate tone and language
- Clear structure and organization
- Correct grammar and spelling
- Helpful and informative content
- Absence of filler words or unnecessary verbosity

Query: {{query}}
Response: {{response}}

Output Format (JSON):
{
  "result": <integer from 1 to 5>,
  "reason": "<brief explanation for the score>"
}"""


def create_code_evaluator(project_client):
    """Register the code-based evaluator in the project's evaluator catalog."""
    print("\n📝 Creating code-based evaluator: response_quality_checker")

    evaluator = project_client.beta.evaluators.create_version(
        name=CODE_EVALUATOR_NAME,
        evaluator_version={
            "name": CODE_EVALUATOR_NAME,
            "categories": [EvaluatorCategory.QUALITY],
            "display_name": "Response Quality Checker",
            "description": (
                "Deterministic quality checker that validates response length, "
                "sentence structure, formatting, and absence of repetition. "
                "Returns 0.0-1.0 based on proportion of checks passed."
            ),
            "definition": {
                "type": EvaluatorDefinitionType.CODE,
                "code_text": CODE_EVALUATOR_SOURCE,
                "init_parameters": {
                    "type": "object",
                    "properties": {
                        "deployment_name": {"type": "string"},
                        "pass_threshold": {"type": "number"},
                    },
                    "required": ["deployment_name", "pass_threshold"],
                },
                "metrics": {
                    "result": {
                        "type": "continuous",
                        "desirable_direction": "increase",
                        "min_value": 0.0,
                        "max_value": 1.0,
                    }
                },
                "data_schema": {
                    "type": "object",
                    "required": ["item"],
                    "properties": {
                        "item": {
                            "type": "object",
                            "properties": {
                                "response": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    )
    print(f"   ✅ Created: {evaluator.name} (version {evaluator.version})")
    return evaluator


def create_prompt_evaluator(project_client):
    """Register the prompt-based evaluator in the project's evaluator catalog."""
    print("\n📝 Creating prompt-based evaluator: professionalism_scorer")

    evaluator = project_client.beta.evaluators.create_version(
        name=PROMPT_EVALUATOR_NAME,
        evaluator_version={
            "name": PROMPT_EVALUATOR_NAME,
            "categories": [EvaluatorCategory.QUALITY],
            "display_name": "Professionalism Scorer",
            "description": (
                "LLM-judged evaluator that rates the professionalism of responses "
                "on a 1-5 scale, considering tone, structure, grammar, and helpfulness."
            ),
            "definition": {
                "type": EvaluatorDefinitionType.PROMPT,
                "prompt_text": PROMPT_EVALUATOR_TEXT,
                "init_parameters": {
                    "type": "object",
                    "properties": {
                        "deployment_name": {"type": "string"},
                        "threshold": {"type": "number"},
                    },
                    "required": ["deployment_name", "threshold"],
                },
                "data_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "response": {"type": "string"},
                    },
                    "required": ["response"],
                },
                "metrics": {
                    "custom_prompt": {
                        "type": "ordinal",
                        "desirable_direction": "increase",
                        "min_value": 1,
                        "max_value": 5,
                    }
                },
            },
        },
    )
    print(f"   ✅ Created: {evaluator.name} (version {evaluator.version})")
    return evaluator


def main():
    print("=" * 60)
    print("DEMO 5c — Custom Evaluators (Code-based + Prompt-based)")
    print("=" * 60)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Create custom evaluators
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 60)
        print("STEP 1: Register custom evaluators in the project catalog")
        print("─" * 60)

        code_eval = create_code_evaluator(project_client)
        prompt_eval = create_prompt_evaluator(project_client)

        # ═══════════════════════════════════════════════════════════
        # STEP 2: Define evaluation with custom + built-in evaluators
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 60)
        print("STEP 2: Configure evaluation (custom + built-in evaluators)")
        print("─" * 60)

        data_source_config = DataSourceConfigCustom(
            type="custom",
            item_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                },
                "required": ["query", "response"],
            },
        )

        testing_criteria = [
            # ── Custom: Code-based evaluator ────────────────────
            {
                "type": "azure_ai_evaluator",
                "name": "response_quality_checker",
                "evaluator_name": CODE_EVALUATOR_NAME,  # References our registered evaluator
                "initialization_parameters": {
                    "deployment_name": MODEL,
                    "pass_threshold": 0.6,  # At least 3 of 5 checks must pass
                },
            },
            # ── Custom: Prompt-based evaluator ──────────────────
            {
                "type": "azure_ai_evaluator",
                "name": "professionalism_scorer",
                "evaluator_name": PROMPT_EVALUATOR_NAME,  # References our registered evaluator
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                },
                "initialization_parameters": {
                    "deployment_name": MODEL,
                    "threshold": 3,  # Score ≥ 3 = pass
                },
            },
            # ── Built-in: For comparison ────────────────────────
            {
                "type": "azure_ai_evaluator",
                "name": "builtin_coherence",
                "evaluator_name": "builtin.coherence",
                "initialization_parameters": {"deployment_name": MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                },
            },
            {
                "type": "azure_ai_evaluator",
                "name": "builtin_fluency",
                "evaluator_name": "builtin.fluency",
                "initialization_parameters": {"deployment_name": MODEL},
                "data_mapping": {
                    "response": "{{item.response}}",
                },
            },
        ]

        print(f"\n   Evaluators: {len(testing_criteria)} total")
        print(f"     Custom code-based:  response_quality_checker (pass_threshold=0.6)")
        print(f"     Custom prompt-based: professionalism_scorer (threshold=3)")
        print(f"     Built-in:           coherence, fluency")

        # ═══════════════════════════════════════════════════════════
        # STEP 3: Create evaluation and run
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 60)
        print("STEP 3: Create evaluation and run with test data")
        print("─" * 60)

        eval_object = openai_client.evals.create(
            name="Custom Evaluators Demo",
            data_source_config=data_source_config,
            testing_criteria=testing_criteria,
        )
        print(f"\n   Eval created: id={eval_object.id}")

        # Test data: varied quality responses to exercise our evaluators
        test_data = [
            # High quality, professional response
            SourceFileContentContent(item={
                "query": "What are the benefits of cloud computing for small businesses?",
                "response": (
                    "Cloud computing offers several key advantages for small businesses. "
                    "First, it significantly reduces upfront infrastructure costs by eliminating "
                    "the need for on-premises servers. Second, it provides scalability, allowing "
                    "businesses to adjust resources based on demand. Third, it enables remote "
                    "work by making applications accessible from anywhere. Finally, cloud providers "
                    "handle security updates and maintenance, freeing up limited IT resources."
                ),
            }),
            # Short, casual response (should score lower on professionalism)
            SourceFileContentContent(item={
                "query": "How do I set up a database?",
                "response": "just use postgres lol, its easy",
            }),
            # Decent but could be more structured
            SourceFileContentContent(item={
                "query": "Explain microservices architecture.",
                "response": (
                    "Microservices architecture breaks down applications into small, independent "
                    "services that communicate via APIs. Each service handles a specific function "
                    "and can be deployed independently. This approach improves scalability and "
                    "makes it easier to update individual components without affecting the whole system."
                ),
            }),
            # Very short and unhelpful
            SourceFileContentContent(item={
                "query": "What is the difference between SQL and NoSQL databases?",
                "response": "They are different.",
            }),
            # Good technical response
            SourceFileContentContent(item={
                "query": "How do you implement authentication in a REST API?",
                "response": (
                    "There are several approaches to implementing authentication in a REST API. "
                    "The most common methods include: 1) OAuth 2.0 with JWT tokens, which provides "
                    "secure, stateless authentication; 2) API keys for simple service-to-service "
                    "communication; 3) Basic authentication over HTTPS for simple use cases. "
                    "For production applications, OAuth 2.0 with short-lived access tokens and "
                    "refresh tokens is recommended. Always use HTTPS to encrypt credentials in transit."
                ),
            }),
        ]

        print(f"   Running with {len(test_data)} test queries...")

        eval_run = openai_client.evals.runs.create(
            eval_id=eval_object.id,
            name="Custom Evaluators Run",
            data_source=CreateEvalJSONLRunDataSourceParam(
                type="jsonl",
                source=SourceFileContent(
                    type="file_content",
                    content=test_data,
                ),
            ),
        )
        print(f"   Run created: id={eval_run.id}")

        # ═══════════════════════════════════════════════════════════
        # STEP 4: Poll and display results
        # ═══════════════════════════════════════════════════════════
        print("\n" + "─" * 60)
        print("STEP 4: Wait for results")
        print("─" * 60)

        print(f"\n   ⏳ Waiting for evaluation to complete...")
        while True:
            run = openai_client.evals.runs.retrieve(
                run_id=eval_run.id, eval_id=eval_object.id
            )
            if run.status in ("completed", "failed"):
                break
            time.sleep(5)
            print(f"   Status: {run.status}")

        if run.status == "completed":
            print(f"\n{'=' * 60}")
            print(f"📊 EVALUATION RESULTS")
            print(f"{'=' * 60}")

            if hasattr(run, "result_counts") and run.result_counts:
                print(f"\n   Overall: {run.result_counts}")

            if hasattr(run, "per_testing_criteria_results") and run.per_testing_criteria_results:
                print(f"\n   Per-evaluator breakdown:")
                for cr in run.per_testing_criteria_results:
                    print(f"     • {cr}")

            # Get per-item details
            print(f"\n   Per-item details:")
            output_items = list(
                openai_client.evals.runs.output_items.list(
                    run_id=run.id, eval_id=eval_object.id
                )
            )
            for i, item in enumerate(output_items):
                query = item.datasource_item.get("query", "N/A")[:60]
                print(f"\n   ── Item {i+1}: \"{query}...\"")
                if hasattr(item, "results") and item.results:
                    for r in item.results:
                        name = r.get("name", "?")
                        passed = "✅" if r.get("passed") else "❌"
                        score = r.get("score", r.get("label", "N/A"))
                        reason = r.get("reason", "")[:80]
                        print(f"      {passed} {name}: score={score} | {reason}")

            if hasattr(run, "report_url") and run.report_url:
                print(f"\n   📎 Full report: {run.report_url}")
        else:
            print(f"\n   ❌ Evaluation {run.status}")
            if hasattr(run, "error") and run.error:
                print(f"   Error: {run.error}")

        # ═══════════════════════════════════════════════════════════
        # List evaluators in the catalog to confirm registration
        # ═══════════════════════════════════════════════════════════
        print(f"\n{'─' * 60}")
        print(f"📚 Custom evaluators now in your project's catalog:")
        print(f"{'─' * 60}")
        print(f"   • {CODE_EVALUATOR_NAME} (code-based, version {code_eval.version})")
        print(f"   • {PROMPT_EVALUATOR_NAME} (prompt-based, version {prompt_eval.version})")
        print(f"   View them in Foundry portal → Evaluation → Evaluator catalog")

    print("\n✅ Demo 5c complete.")


if __name__ == "__main__":
    main()
