"""
Demo 2c — Agent with the built-in Code Interpreter tool

This demo shows how to:
  1. Use CodeInterpreterTool — a built-in Foundry tool (no setup needed)
  2. The agent can write and execute Python code in a sandboxed environment
  3. Extract the generated code from the response output

Use cases: data analysis, math, chart generation, file processing.
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, CodeInterpreterTool

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
AGENT_NAME = "demo-code-interpreter-agent"


def main():
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project_client,
    ):
        with project_client.get_openai_client() as openai_client:

            print("=" * 60)
            print("DEMO 2c — Agent with Code Interpreter Tool")
            print("=" * 60)

            # ── Create agent with Code Interpreter ──────────────────
            tool = CodeInterpreterTool()

            agent = project_client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=MODEL,
                    instructions=(
                        "You are a data analyst. When asked analytical or mathematical "
                        "questions, use the code interpreter to write and run Python code "
                        "to compute the answer. Show your work."
                    ),
                    tools=[tool],
                ),
            )
            print(f"\n📌 Agent created with CodeInterpreter: name={agent.name}")

            # ── Create conversation ─────────────────────────────────
            conversation = openai_client.conversations.create()

            # ── Turn 1: Ask a math question ─────────────────────────
            question = "Calculate the first 20 Fibonacci numbers and tell me which ones are prime."
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": question}],
            )
            print(f"\n[Turn 1] Q: {question}")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )

            # Extract the generated code from code_interpreter_call output
            code = next(
                (output.code for output in response.output if output.type == "code_interpreter_call"),
                None,
            )
            if code:
                print(f"\n  💻 Generated code:")
                print("  " + "\n  ".join(code.splitlines()))

            print(f"\n[Turn 1] A: {response.output_text}")

            # ── Turn 2: Follow-up analysis ──────────────────────────
            question2 = "Now plot a bar chart of those 20 Fibonacci numbers. Describe the growth pattern."
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": question2}],
            )
            print(f"\n[Turn 2] Q: {question2}")

            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
            )

            code = next(
                (output.code for output in response.output if output.type == "code_interpreter_call"),
                None,
            )
            if code:
                print(f"\n  💻 Generated code:")
                print("  " + "\n  ".join(code.splitlines()))

            print(f"\n[Turn 2] A: {response.output_text}")

            # ── Cleanup ─────────────────────────────────────────────
            openai_client.conversations.delete(conversation_id=conversation.id)
            print(f"\n🗑️  Conversation deleted.")

        project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        print(f"🗑️  Agent version deleted.")

    print("\n✅ Demo 2c complete.")


if __name__ == "__main__":
    main()
