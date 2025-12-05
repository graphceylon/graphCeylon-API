# LLM Abstraction Layer

## Overview

The LLM abstraction layer provides flexible provider management for using different LLMs across different parts of the application. This allows you to optimize costs and performance by using specialized models for specific tasks.

## Architecture

### Components

1. **LLMProvider (Abstract Base Class)**
   - Defines interface for all LLM providers
   - Methods: `get_chat_model()`, `supports_structured_output()`

2. **Provider Implementations**
   - `OpenAIProvider`: OpenAI models (GPT-4, GPT-3.5, etc.)
   - `GroqProvider`: Groq models (Llama 3.3, Mixtral, etc.)

3. **LLMFactory**
   - Creates provider instances based on configuration
   - Supports multiple provider types
   - Validates provider configurations

## Configuration

### Environment Variables

```env
# API Keys
KG_OPENAI_API_KEY=sk-...
KG_GROQ_API_KEY=gsk_...

# Ingestion Configuration (Entity Extraction)
KG_INGESTION_LLM_PROVIDER=openai
KG_INGESTION_LLM_MODEL=gpt-4o-mini

# Query Configuration (RAG Chatbot)
KG_QUERY_LLM_PROVIDER=groq
KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile

# Temperature Setting
KG_LLM_TEMPERATURE=0
```

### Use Cases

#### Use Case 1: OpenAI for Ingestion, Groq for Queries (Recommended)

**Why:** OpenAI's structured output is excellent for entity extraction, while Groq's fast inference is perfect for real-time chatbot responses.

```env
KG_INGESTION_LLM_PROVIDER=openai
KG_INGESTION_LLM_MODEL=gpt-4o-mini
KG_QUERY_LLM_PROVIDER=groq
KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile
```

**Benefits:**
- Fast chatbot responses (Groq's high throughput)
- Accurate entity extraction (OpenAI's structured output)
- Cost-effective (cheaper ingestion model, free Groq for queries)

#### Use Case 2: All OpenAI

```env
KG_INGESTION_LLM_PROVIDER=openai
KG_INGESTION_LLM_MODEL=gpt-4o-mini
KG_QUERY_LLM_PROVIDER=openai
KG_QUERY_LLM_MODEL=gpt-4o
```

**Benefits:**
- Consistent behavior across all operations
- Best accuracy for complex queries
- Single API key management

#### Use Case 3: All Groq

```env
KG_INGESTION_LLM_PROVIDER=groq
KG_INGESTION_LLM_MODEL=llama-3.3-70b-versatile
KG_QUERY_LLM_PROVIDER=groq
KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile
```

**Benefits:**
- Free tier with high rate limits
- Extremely fast inference
- Good for development/testing

## Code Structure

### Directory Layout

```
services/llm/
├── __init__.py         # Package exports
├── providers.py        # Provider implementations
└── factory.py          # Factory for creating providers
```

### Usage in GraphRAG

**Entity Extractor** (`services/graphrag/entity_extractor.py`):
```python
from services.llm import LLMFactory
from core.config import settings

# Gets configured ingestion provider and model
provider = LLMFactory.create_from_config(
    settings.ingestion_llm_provider,
    api_key
)
llm = provider.get_chat_model(
    model=settings.ingestion_llm_model,
    temperature=settings.llm_temperature
)
```

**RAG Query Engine** (`services/graphrag/rag_query_engine.py`):
```python
from services.llm import LLMFactory
from core.config import settings

# Gets configured query provider and model
provider = LLMFactory.create_from_config(
    settings.query_llm_provider,
    api_key
)
llm = provider.get_chat_model(
    model=settings.query_llm_model,
    temperature=settings.llm_temperature
)
```

## Supported Models

### OpenAI
- `gpt-4o`: Most capable, best for complex reasoning
- `gpt-4o-mini`: Fast and cost-effective
- `gpt-4-turbo`: Previous generation, still very capable
- `gpt-3.5-turbo`: Cheapest, good for simple tasks

### Groq
- `llama-3.3-70b-versatile`: Best quality, 128K context
- `llama-3.1-70b-versatile`: Good quality, fast
- `mixtral-8x7b-32768`: Fast, 32K context
- `gemma2-9b-it`: Lightweight, very fast

## Adding New Providers

To add a new provider (e.g., Anthropic Claude):

1. **Create Provider Class** in `services/llm/providers.py`:
```python
class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_chat_model(self, model: str = "claude-3-5-sonnet-20241022", temperature: float = 0):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=self.api_key
        )
    
    def supports_structured_output(self) -> bool:
        return True
```

2. **Update Enum** in `services/llm/factory.py`:
```python
class LLMProviderType(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"
    CLAUDE = "claude"  # Add new type
```

3. **Update Factory** in `services/llm/factory.py`:
```python
def create_provider(provider_type: LLMProviderType, api_key: str) -> LLMProvider:
    if provider_type == LLMProviderType.CLAUDE:
        return ClaudeProvider(api_key)
    # ... existing code
```

4. **Add Configuration** in `core/config.py`:
```python
claude_api_key: Optional[str] = None
```

5. **Update Requirements**:
```
langchain-anthropic
```

## API Validation

The GraphRAG API validates that required API keys are configured before initializing:

```python
# Checks that ingestion provider has valid API key
if settings.ingestion_llm_provider == "openai" and not settings.openai_api_key:
    raise HTTPException(status_code=503, detail="OpenAI API key required")

# Checks that query provider has valid API key
if settings.query_llm_provider == "groq" and not settings.groq_api_key:
    raise HTTPException(status_code=503, detail="Groq API key required")
```

## Performance Comparison

| Provider | Model | Speed | Cost | Quality |
|----------|-------|-------|------|---------|
| OpenAI | gpt-4o | ⭐⭐⭐ | $$$ | ⭐⭐⭐⭐⭐ |
| OpenAI | gpt-4o-mini | ⭐⭐⭐⭐ | $ | ⭐⭐⭐⭐ |
| Groq | llama-3.3-70b | ⭐⭐⭐⭐⭐ | Free | ⭐⭐⭐⭐ |
| Groq | mixtral-8x7b | ⭐⭐⭐⭐⭐ | Free | ⭐⭐⭐ |

## Best Practices

1. **Use OpenAI for Ingestion**: Better structured output support for entity extraction
2. **Use Groq for Queries**: Faster responses for real-time chatbot interactions
3. **Set Temperature to 0**: For deterministic, consistent outputs
4. **Monitor Rate Limits**: Both providers have rate limits
5. **Test Both Providers**: Validate quality meets your requirements

## Troubleshooting

### Error: "Failed to initialize LLM"
- Check API key is valid and active
- Verify provider name is correct (lowercase)
- Ensure langchain package for provider is installed

### Error: "Provider type not supported"
- Provider must be "openai" or "groq"
- Check environment variable spelling

### Slow Response Times
- Try Groq for faster inference
- Check network latency
- Consider using smaller models

### Quality Issues
- Try gpt-4o for better accuracy
- Adjust temperature (higher = more creative, lower = more deterministic)
- Verify prompt engineering is optimal
