# Observability Guide — Tracing in Microsoft Foundry

Complete reference for configuring tracing and observability with the Foundry SDK v2.

## Overview

Tracing lets you see every step of your AI application: LLM calls, tool invocations, agent reasoning, and custom function execution. Foundry uses OpenTelemetry for tracing.

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRACING ARCHITECTURE                        │
│                                                                 │
│  Your Code  ──→  AIProjectInstrumentor  ──→  TracerProvider     │
│                  (patches SDK calls)         │                  │
│                                              ├─→ Console        │
│                                              ├─→ Azure Monitor  │
│                                              └─→ OTLP endpoint  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Console Tracing (Demo 4a)

See traces in your terminal — great for development and debugging:

```python
import os
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"

from azure.ai.projects.telemetry import AIProjectInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Setup
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

# Instrument the SDK
AIProjectInstrumentor().instrument()
```

### Azure Monitor (Demo 4b)

Send traces to Application Insights — view in Foundry portal:

```python
import os
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"

from azure.ai.projects.telemetry import AIProjectInstrumentor
from azure.monitor.opentelemetry import configure_azure_monitor

# Get connection string from your project
conn_string = project_client.telemetry.get_application_insights_connection_string()
configure_azure_monitor(connection_string=conn_string)

# Instrument the SDK
AIProjectInstrumentor().instrument()
```

---

## Environment Variables

All tracing-related environment variables must be set **before** calling `AIProjectInstrumentor().instrument()`.

| Variable | Default | Description |
|---|---|---|
| `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING` | `false` | **Required**. Must be `true` to enable tracing. |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | `false` | Capture message contents in traces (may include sensitive data). |
| `AZURE_TRACING_GEN_AI_ENABLE_TRACE_CONTEXT_PROPAGATION` | `false` | Propagate trace context (traceparent/tracestate) to Azure OpenAI. |
| `AZURE_TRACING_GEN_AI_TRACE_CONTEXT_PROPAGATION_INCLUDE_BAGGAGE` | `false` | Also propagate baggage header (may contain PII — use with caution). |
| `AZURE_TRACING_GEN_AI_INCLUDE_BINARY_DATA` | `false` | Include image/file data in traces (increases trace size significantly). |
| `AZURE_TRACING_GEN_AI_INSTRUMENT_RESPONSES_API` | `true` | Auto-instrument responses/conversations API. Set `false` to disable. |

### Security Considerations

- **Content recording** (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`): When enabled, prompts and responses are captured. Disable in production with sensitive data.
- **Trace context propagation**: Sends trace IDs to Azure OpenAI. Enables end-to-end distributed tracing but has privacy implications.
- **Baggage propagation**: May contain user identifiers, session data, or PII. Disabled by default even when trace context propagation is enabled.
- **Binary data**: Can significantly increase trace sizes. Ensure your backend supports large payloads.

---

## Tracing Custom Functions

Use the `@trace_function` decorator to trace your own functions:

```python
from azure.ai.projects.telemetry import trace_function

@trace_function("my_custom_operation")
def lookup_data(query: str) -> str:
    """This function will appear as a span in your traces."""
    return f"Result for {query}"
```

The decorator automatically records:
- Function parameters as span attributes (`code.function.parameter.<name>`)
- Return value as span attribute (`code.function.return.value`)
- Supported types: `str`, `int`, `float`, `bool`, `list`, `dict`, `tuple`, `set`

> **Note**: `@trace_function` always captures parameters regardless of the `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` setting.

---

## Creating Custom Spans

Wrap scenarios in spans for easy identification in your observability backend:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("my_scenario"):
    # All SDK calls within this block are children of this span
    response = openai_client.responses.create(...)
```

---

## Custom Span Attributes

Add custom attributes to spans for filtering and grouping:

```python
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.trace import Span
from opentelemetry.sdk.trace.export import ReadableSpan

class CustomAttributeSpanProcessor(SpanProcessor):
    def on_start(self, span: Span, parent_context=None):
        span.set_attribute("app.session_id", "abc123")
        span.set_attribute("app.user_tier", "premium")

    def on_end(self, span: ReadableSpan):
        pass

# Add to provider
provider = trace.get_tracer_provider()
provider.add_span_processor(CustomAttributeSpanProcessor())
```

---

## Exporters

### Console (development)

```python
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
```

### Azure Monitor / Application Insights (production)

```bash
pip install azure-monitor-opentelemetry
```

```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(connection_string="InstrumentationKey=...")
```

### OTLP (Aspire Dashboard, Jaeger, etc.)

```bash
pip install opentelemetry-exporter-otlp
```

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
)
```

---

## What Gets Traced

When `AIProjectInstrumentor().instrument()` is called, the SDK automatically instruments:

| Operation | Span Name Pattern | Details |
|---|---|---|
| Model response | `chat {model_name}` | LLM call with input/output messages |
| Agent invocation | `invoke_agent {agent_name}` | Agent call with conversation context |
| Agent creation | `create_agent` | Agent definition + system instructions |
| Conversation operations | Various | Create, list items, delete |
| Tool calls | Nested spans | Function calls, code interpreter, etc. |

### Span Attributes

Key attributes available on spans:

| Attribute | Description |
|---|---|
| `gen_ai.provider.name` | `microsoft.foundry` |
| `gen_ai.agent.name` | Agent name (for agent calls) |
| `gen_ai.system_instructions` | Agent instructions |
| `gen_ai.input.messages` | Input messages (if content recording enabled) |
| `gen_ai.output.messages` | Output messages (if content recording enabled) |

---

## Viewing Traces

### Foundry Portal

1. Go to your Microsoft Foundry project
2. Navigate to the **Tracing** tab
3. Traces appear within 2-5 minutes

> **Important**: To see agent traces in the portal, the agent ID must be passed as part of the response generation request (this happens automatically when using `agent_reference`).

### Azure Monitor / Application Insights

1. Go to the Azure portal → your Application Insights resource
2. Use **Transaction Search** or **Performance** to explore traces
3. Filter by custom attributes if you added any

### Aspire Dashboard (local)

```bash
docker run --rm -p 18888:18888 -p 4317:18889 mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

Then set `OTEL_EXPORTER_ENDPOINT=http://localhost:4317` and use the OTLP exporter.

---

## Packages Required

```
azure-ai-projects>=2.0.0
opentelemetry-sdk
azure-core-tracing-opentelemetry
azure-monitor-opentelemetry          # For Azure Monitor export
opentelemetry-exporter-otlp          # For OTLP export (Aspire, Jaeger, etc.)
```

## Further Reading

- [Agent tracing overview](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-agent-concept)
- [Trace setup guide](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup)
- [Agent monitoring dashboard](https://learn.microsoft.com/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard)
