# LLM Abstraction Layer - Setup Guide

## What Was Created

You now have a flexible LLM abstraction layer that allows you to use **OpenAI for data ingestion** and **Groq for querying**. This optimizes both cost and performance.

## Files Created

### 1. Core Abstraction Layer
- `src/services/llm/__init__.py` - Package exports
- `src/services/llm/providers.py` - OpenAI and Groq provider implementations
- `src/services/llm/factory.py` - Factory for creating providers

### 2. Updated Files
- `src/core/config.py` - Added LLM configuration settings
- `src/services/graphrag/config.py` - Removed hardcoded LLM settings
- `src/services/graphrag/entity_extractor.py` - Uses ingestion LLM
- `src/services/graphrag/rag_query_engine.py` - Uses query LLM
- `src/services/graphrag/service.py` - Simplified initialization
- `src/api/graphrag.py` - Validates API keys for both providers
- `requirements.txt` - Added langchain-groq
- `.env.example` - Added Groq and LLM configuration

### 3. Documentation
- `docs/LLM_ABSTRACTION.md` - Comprehensive guide

## Configuration

### Step 1: Update Your .env File

Add these new variables to your `.env` file:

```env
# API Keys
KG_OPENAI_API_KEY=sk-your-openai-key-here
KG_GROQ_API_KEY=gsk_your-groq-key-here

# Ingestion Configuration (Entity Extraction)
KG_INGESTION_LLM_PROVIDER=openai
KG_INGESTION_LLM_MODEL=gpt-4o-mini

# Query Configuration (RAG Chatbot)
KG_QUERY_LLM_PROVIDER=groq
KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile

# Temperature Setting
KG_LLM_TEMPERATURE=0
```

### Step 2: Get Groq API Key

1. Visit https://console.groq.com/
2. Sign up for free account
3. Navigate to API Keys section
4. Create new API key
5. Copy and paste into your `.env` file

### Step 3: Verify Installation

The `langchain-groq` package is already installed. You're ready to go!

## How It Works

### Data Ingestion (Entity Extraction)
- **Provider**: OpenAI (gpt-4o-mini)
- **Purpose**: Extract entities and relationships from immigration data
- **Why**: OpenAI's structured output is excellent for complex entity extraction
- **Location**: `services/graphrag/entity_extractor.py`

### Querying (RAG Chatbot)
- **Provider**: Groq (llama-3.3-70b-versatile)
- **Purpose**: Answer user questions using knowledge graph
- **Why**: Groq is ultra-fast (perfect for real-time chat) and free
- **Location**: `services/graphrag/rag_query_engine.py`

## Testing

### 1. Start the API Server

```powershell
cd d:\projects\graphCeylon-API\services\kg_service
python src/main.py
```

### 2. Test Entity Extraction (Uses OpenAI)

```powershell
curl -X POST http://localhost:8000/graphrag/ingest `
  -H "Content-Type: application/json" `
  -d '{
    "data_dir": "data/immigration",
    "domain_name": "Economic & Policy"
  }'
```

**Expected**: OpenAI (gpt-4o-mini) extracts entities from immigration data

### 3. Test RAG Query (Uses Groq)

```powershell
curl -X POST http://localhost:8000/graphrag/query `
  -H "Content-Type: application/json" `
  -d '{
    "question": "What are the fees for dual citizenship?",
    "domain_name": "Economic & Policy",
    "top_k": 5
  }'
```

**Expected**: Groq (llama-3.3-70b-versatile) answers using knowledge graph

## Configuration Options

### Option 1: OpenAI + Groq (Recommended)

```env
KG_INGESTION_LLM_PROVIDER=openai
KG_INGESTION_LLM_MODEL=gpt-4o-mini
KG_QUERY_LLM_PROVIDER=groq
KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile
```

**Benefits:**
- ⚡ Fast chatbot responses (Groq)
- ✅ Accurate entity extraction (OpenAI)
- 💰 Cost-effective (cheap ingestion + free queries)

### Option 2: All OpenAI

```env
KG_INGESTION_LLM_PROVIDER=openai
KG_INGESTION_LLM_MODEL=gpt-4o-mini
KG_QUERY_LLM_PROVIDER=openai
KG_QUERY_LLM_MODEL=gpt-4o
```

**Benefits:**
- 🎯 Maximum accuracy
- 🔄 Consistent behavior
- 🔑 Single API key

### Option 3: All Groq

```env
KG_INGESTION_LLM_PROVIDER=groq
KG_INGESTION_LLM_MODEL=llama-3.3-70b-versatile
KG_QUERY_LLM_PROVIDER=groq
KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile
```

**Benefits:**
- 💸 Completely free
- ⚡⚡⚡ Ultra-fast
- 🧪 Perfect for development

## Available Models

### OpenAI Models
- `gpt-4o` - Most capable ($0.005/1K input)
- `gpt-4o-mini` - **Recommended** ($0.00015/1K input)
- `gpt-4-turbo` - Previous gen ($0.01/1K input)
- `gpt-3.5-turbo` - Cheapest ($0.0005/1K input)

### Groq Models (All Free!)
- `llama-3.3-70b-versatile` - **Recommended** (128K context)
- `llama-3.1-70b-versatile` - Fast and capable
- `mixtral-8x7b-32768` - Very fast (32K context)
- `gemma2-9b-it` - Lightweight and fast

## Architecture Flow

```
┌─────────────────────────────────────────────┐
│         FastAPI Application                 │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         GraphRAG Service                    │
└─────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐
│ EntityExtractor │    │  RAGQueryEngine     │
│                 │    │                     │
│ Uses: Ingestion │    │ Uses: Query LLM     │
│ LLM (OpenAI)    │    │ (Groq)              │
└─────────────────┘    └─────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐
│  LLMFactory     │    │  LLMFactory         │
│  ↓              │    │  ↓                  │
│  OpenAIProvider │    │  GroqProvider       │
└─────────────────┘    └─────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐
│  gpt-4o-mini    │    │  llama-3.3-70b      │
│  (Entity        │    │  (Answer            │
│   Extraction)   │    │   Questions)        │
└─────────────────┘    └─────────────────────┘
```

## Troubleshooting

### "Groq API key not configured"
- Check your `.env` file has `KG_GROQ_API_KEY=gsk_...`
- Restart the server after updating `.env`
- Verify the API key is valid at console.groq.com

### "Failed to initialize LLM"
- Check the provider name is lowercase: `openai` or `groq`
- Verify the model name is correct
- Check network connectivity

### Slow Responses
- If using OpenAI for queries, switch to Groq:
  ```env
  KG_QUERY_LLM_PROVIDER=groq
  KG_QUERY_LLM_MODEL=llama-3.3-70b-versatile
  ```

### Quality Issues
- Try a more capable model:
  ```env
  KG_QUERY_LLM_MODEL=gpt-4o  # If using OpenAI
  ```
- Check your prompts in the code
- Verify the knowledge graph has good data

## Next Steps

1. ✅ Add Groq API key to `.env`
2. ✅ Restart API server
3. ✅ Test data ingestion (uses OpenAI)
4. ✅ Test querying (uses Groq)
5. ✅ Monitor performance and costs
6. ✅ Adjust configuration as needed

## Cost Comparison

**Example: 1000 questions/day for 30 days**

### All OpenAI (gpt-4o-mini)
- Ingestion: ~$0.50 (one-time)
- Queries: ~$4.50/month
- **Total: ~$5/month**

### OpenAI + Groq (Recommended)
- Ingestion: ~$0.50 (one-time)
- Queries: **FREE**
- **Total: ~$0.50 one-time**

### All Groq
- Ingestion: **FREE**
- Queries: **FREE**
- **Total: $0**

## Support

For more details, see:
- `docs/LLM_ABSTRACTION.md` - Full technical documentation
- OpenAI Docs: https://platform.openai.com/docs
- Groq Docs: https://console.groq.com/docs
- LangChain Docs: https://python.langchain.com/docs/

## Summary

You now have a production-ready LLM abstraction layer that:
- ✅ Uses OpenAI for accurate entity extraction
- ✅ Uses Groq for fast, free chatbot responses
- ✅ Easily configurable via environment variables
- ✅ Supports multiple providers and models
- ✅ Optimizes both cost and performance
- ✅ Production-ready with proper error handling

**Next**: Add your Groq API key to `.env` and restart the server!
