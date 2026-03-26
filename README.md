# Microsoft Foundry SDK v2 — Demo Suite

Hands-on demos covering the core capabilities of the **Microsoft Foundry SDK v2** (`azure-ai-projects >= 2.0.0`).

## Prerequisites

- **Azure subscription** with a [Microsoft Foundry project](https://learn.microsoft.com/azure/foundry/how-to/create-projects)
- At least one **model deployed** in your Foundry project (e.g. `gpt-4o`)
- **Azure CLI** installed and logged in (`az login`)
- **Python 3.10+**

## Quick Start

```bash
# 1. Copy the environment template and fill in your values
cp .env.template .env
# Edit .env with your project endpoint and model deployment name

# 2. Install dependencies (handled automatically by the DevContainer)
pip install -r requirements.txt

# 3. Run any demo
python demo1_llm_consumption/1a_foundry_responses.py
```

## Project Structure

```
├── .env.template                          # Configuration template (copy to .env)
├── requirements.txt                       # Python dependencies
│
├── demo1_llm_consumption/                 # Demo 1: LLM Consumption
│   ├── 1a_foundry_responses.py            #   → Foundry SDK + Responses API
│   ├── 1b_openai_native.py               #   → Direct OpenAI SDK + Chat Completions
│   └── 1c_model_router.py                #   → Model Router (smart multi-model routing)
│
├── demo2_agents/                          # Demo 2: Foundry Agents
│   ├── 2a_basic_agent.py                  #   → Basic agent + multi-turn conversation
│   ├── 2b_agent_function_tool.py          #   → Agent with custom FunctionTool
│   ├── 2c_agent_code_interpreter.py       #   → Agent with Code Interpreter
│   └── 2d_agent_mcp_tools.py              #   → Agent with MCP tools (Learn + GitMCP)
│
├── demo3_hosted_agent/                    # Demo 3: Hosted Agents
│   ├── agent_app.py                       #   → Agent code (Microsoft Agent Framework)
│   ├── Dockerfile                         #   → Container image definition
│   ├── requirements_hosted.txt            #   → Container dependencies
│   └── 3_deploy_hosted_agent.py           #   → SDK script to register the agent
│
├── demo4_observability/                   # Demo 4: Observability
│   ├── 4a_console_tracing.py             #   → OpenTelemetry traces to console
│   └── 4b_azure_monitor_tracing.py       #   → Traces to Azure Monitor / App Insights
│
└── demo5_evaluation/                      # Demo 5: Evaluation
    ├── 5a_evaluate_llm.py                 #   → Evaluate LLM responses
    └── 5b_evaluate_agent.py               #   → Evaluate an agent
```

## Demo Details

### Demo 1 — LLM Consumption

Shows two ways to call an LLM, highlighting the differences:

| | **1a: Foundry SDK** | **1b: Direct OpenAI SDK** | **1c: Model Router** |
|---|---|---|---|
| Client | `AIProjectClient` → `get_openai_client()` | `AzureOpenAI` (manual setup) | `AIProjectClient` → `get_openai_client()` |
| API | Responses API (`responses.create`) | Chat Completions (`chat.completions.create`) | Chat Completions (router uses this API) |
| Model | Single fixed model | Single fixed model | Router selects best model per-prompt |
| Multi-turn | `previous_response_id` | Manual message list | Manual message list |
| Metadata | Basic | Basic | Full: model selected, tokens, latency |

```bash
python demo1_llm_consumption/1a_foundry_responses.py
python demo1_llm_consumption/1b_openai_native.py
python demo1_llm_consumption/1c_model_router.py
```

### Demo 2 — Foundry Agents

Four progressively more complex agent examples:

- **2a** — Basic agent with multi-turn conversation (create → chat → cleanup)
- **2b** — Agent with a custom `FunctionTool` defined "on the go" (local function calling)
- **2c** — Agent with the built-in `CodeInterpreterTool` (sandboxed Python execution)
- **2d** — Agent with `MCPTool` connecting to external MCP servers (Microsoft Learn + GitMCP)

```bash
python demo2_agents/2a_basic_agent.py
python demo2_agents/2b_agent_function_tool.py
python demo2_agents/2c_agent_code_interpreter.py
python demo2_agents/2d_agent_mcp_tools.py
```

### Demo 3 — Hosted Agents

Deploy your own external agent code as a managed container on Foundry. The script **automates everything**: image build, ACR push, RBAC, capability host, agent registration, and deployment start.

#### Prerequisite

- **Azure Container Registry (ACR)** already created — [Create one](https://learn.microsoft.com/azure/container-registry/container-registry-get-started-portal)
- Fill in `ACR_NAME`, `FOUNDRY_ACCOUNT_NAME`, `FOUNDRY_PROJECT_NAME`, `FOUNDRY_RESOURCE_GROUP` in `.env`

#### Run

```bash
# One command does everything: build → push → RBAC → capability host → register → start
python demo3_hosted_agent/3_deploy_hosted_agent.py
```

The script auto-detects Docker availability. If Docker is not available (e.g. in a DevContainer), it falls back to **ACR Tasks** for a cloud-based build — no local Docker needed.

#### Test locally (optional)

```bash
cd demo3_hosted_agent
pip install -r requirements_hosted.txt
python agent_app.py
# → Runs on http://localhost:8088, test with:
curl -X POST http://localhost:8088/responses -H "Content-Type: application/json" -d '{"input":"What time is it in Tokyo?"}'
```

### Demo 4 — Observability

- **4a** — Console tracing: see every LLM call, tool invocation, and agent step in your terminal
- **4b** — Azure Monitor: send traces to Application Insights (view in Foundry portal → Tracing tab)

```bash
python demo4_observability/4a_console_tracing.py
python demo4_observability/4b_azure_monitor_tracing.py   # Requires App Insights
```

### Demo 5 — Evaluation

- **5a** — Evaluate **model responses** with built-in evaluators (fluency, violence, coherence)
- **5b** — Evaluate an **agent** with task adherence, fluency, and safety metrics

```bash
python demo5_evaluation/5a_evaluate_llm.py
python demo5_evaluation/5b_evaluate_agent.py
```

## Environment Variables

| Variable | Required | Used by | Description |
|---|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | ✅ All demos | All | Foundry project endpoint URL |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | ✅ All demos | All | Model deployment name (e.g. `gpt-4o`) |
| `MODEL_ROUTER_DEPLOYMENT_NAME` | Demo 1c only | `1c_model_router.py` | Model Router deployment name (default: `model-router`) |
| `ACR_NAME` | Demo 3 only | `3_deploy_hosted_agent.py` | ACR name (e.g. `myacr`, not the full `.azurecr.io` URL) |
| `FOUNDRY_ACCOUNT_NAME` | Demo 3 only | `3_deploy_hosted_agent.py` | Foundry account name |
| `FOUNDRY_PROJECT_NAME` | Demo 3 only | `3_deploy_hosted_agent.py` | Foundry project name |
| `FOUNDRY_RESOURCE_GROUP` | Demo 3 only | `3_deploy_hosted_agent.py` | Azure resource group |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Demo 4b only | `4b_azure_monitor_tracing.py` | App Insights connection string (auto-detected if omitted) |

## SDK Version

All demos use **`azure-ai-projects` v2.0.x** (GA, released March 2026). This is incompatible with v1.x — see the [migration guide](https://learn.microsoft.com/azure/foundry/agents/how-to/migrate) if coming from the classic API.
