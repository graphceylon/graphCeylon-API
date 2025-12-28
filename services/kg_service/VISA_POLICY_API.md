# Visa Policy Query API - GraphRAG Retrieval Without LLM

## Overview

This endpoint retrieves visa policy information using **vector similarity search only**, without invoking an LLM for answer generation. It's designed for scenarios where another service handles the final answer synthesis.

## Endpoint

```
POST /graphrag/visa-policy
```

## Flow Diagram

```
User Request (Structured JSON)
    ↓
Build Semantic Query from Fields
    ↓
Generate Query Embedding
    ↓
Vector Similarity Search (Neo4j)
    ↓
Retrieve Top 10 Relevant Chunks (min score: 0.4)
    ↓
Extract Entities & Rules from Chunks
    ↓
Format Structured Response
    ↓
Return (status, summary, rules, warnings)
```

## Request Format

```json
{
  "intent": "info_visa_policy",
  "user_id": "user123",
  "session_id": "test_session_002",
  "raw_text": "I'm an Indian citizen. Do I need a visa to visit Sri Lanka for 10 days in February 2026?",
  "nationality_country": "India",
  "destination_country": "Sri Lanka",
  "intended_stay_days": 10,
  "travel_window": {
    "start_date": "2026-02-01",
    "end_date": "2026-02-28"
  },
  "purpose": "tourism",
  "passport_type": "ordinary",
  "entry_type": null,
  "prior_visa_or_eta": null,
  "ask_type": "eligibility",
  "extra": {
    "domain_category": "visa",
    "confidence": 0.7367
  }
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `intent` | string | Yes | Intent type (e.g., 'info_visa_policy') |
| `user_id` | string | Yes | User identifier |
| `session_id` | string | Yes | Session identifier |
| `raw_text` | string | Yes | User's raw question text |
| `nationality_country` | string | Yes | Nationality/passport country |
| `destination_country` | string | Yes | Destination country |
| `intended_stay_days` | integer | Yes | Intended stay duration in days |
| `travel_window` | object | Yes | Travel date range with start_date and end_date |
| `purpose` | string | Yes | Purpose of travel (tourism, business, etc.) |
| `passport_type` | string | Yes | Type of passport (ordinary, diplomatic, etc.) |
| `entry_type` | string | No | Entry type (single, multiple, etc.) |
| `prior_visa_or_eta` | string | No | Prior visa or ETA status |
| `ask_type` | string | Yes | Type of query (eligibility, requirements, etc.) |
| `extra` | object | No | Extra metadata |

## Response Formats

### 1. Success Response (`status: "ok"`)

```json
{
  "status": "ok",
  "destination_country": "Sri Lanka",
  "nationality_country": "India",
  "purpose": "tourism",
  "passport_type": "ordinary",
  "travel_window": {
    "start_date": "2026-02-01",
    "end_date": "2026-02-28"
  },
  "intended_stay_days": 10,
  "summary": "Indian passport holders require an Electronic Travel Authorization (ETA) to visit Sri Lanka for tourism stays up to 30 days.",
  "rules": [
    {
      "rule_type": "eligibility",
      "title": "Tourist ETA Required",
      "details": "Indian citizens must obtain an ETA prior to arrival. ETA allows a stay of up to 30 days and can be extended while in Sri Lanka.",
      "conditions": {
        "nationality": "India",
        "purpose": "tourism",
        "passport_type": "ordinary",
        "max_stay_days": 30
      },
      "evidence": [
        {
          "source": "immigration.gov.lk",
          "url": "https://www.immigration.gov.lk",
          "quote": "ETA is mandatory for Indian nationals traveling for tourism."
        }
      ]
    }
  ],
  "warnings": [
    "This information is for reference only. Please verify with official immigration authorities before travel."
  ]
}
```

### 2. Needs Clarification (`status: "needs_clarification"`)

```json
{
  "status": "needs_clarification",
  "destination_country": null,
  "nationality_country": null,
  "purpose": null,
  "passport_type": null,
  "travel_window": null,
  "intended_stay_days": null,
  "summary": "Please specify your passport type to determine visa eligibility.",
  "rules": [],
  "warnings": []
}
```

### 3. No Result (`status: "no_result"`)

```json
{
  "status": "no_result",
  "destination_country": "Antarctica",
  "nationality_country": "India",
  "purpose": "tourism",
  "passport_type": "ordinary",
  "travel_window": {
    "start_date": "2026-02-01",
    "end_date": "2026-02-28"
  },
  "intended_stay_days": 10,
  "summary": "No visa rules found for the given criteria.",
  "rules": [],
  "warnings": [
    "Please consult official immigration authorities for the most current visa requirements."
  ]
}
```

### 4. Error Response (`status: "error"`)

```json
{
  "status": "error",
  "destination_country": null,
  "nationality_country": null,
  "purpose": null,
  "passport_type": null,
  "travel_window": null,
  "intended_stay_days": null,
  "summary": "Unable to retrieve visa policy at this time.",
  "rules": [],
  "warnings": []
}
```

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Response status: "ok", "needs_clarification", "no_result", or "error" |
| `destination_country` | string | Destination country (echoed from request) |
| `nationality_country` | string | Nationality country (echoed from request) |
| `purpose` | string | Travel purpose (echoed from request) |
| `passport_type` | string | Passport type (echoed from request) |
| `travel_window` | object | Travel date range (echoed from request) |
| `intended_stay_days` | integer | Intended stay days (echoed from request) |
| `summary` | string | Brief summary of visa requirements |
| `rules` | array | Array of visa rules with details |
| `warnings` | array | Array of warning messages |

### Rule Object

| Field | Type | Description |
|-------|------|-------------|
| `rule_type` | string | Type: eligibility, requirements, fees, procedure, duration, general_information |
| `title` | string | Rule title/heading |
| `details` | string | Detailed description (max 400 chars) |
| `conditions` | object | Applicable conditions |
| `evidence` | array | Supporting evidence sources |

## How It Works

### 1. Query Construction
The endpoint builds a semantic query by combining:
- Raw user text
- Structured fields (nationality, destination, purpose, etc.)
- Example: `"I'm an Indian citizen. Do I need a visa... | Nationality: India | Destination: Sri Lanka | Purpose: tourism..."`

### 2. Vector Search
- Generates embedding for the composite query
- Searches Neo4j for similar chunks using **cosine similarity**
- Retrieves **top 10 chunks** with similarity score > **0.4**
- Includes entities mentioned in each chunk

### 3. Rule Extraction
Analyzes retrieved chunks to extract:
- **Rule type** (eligibility, requirements, fees, etc.) based on keywords
- **Title** and **details** from chunk text
- **Conditions** (nationality, purpose, max stay days)
- **Evidence sources** with quotes

### 4. Summary Generation
- Uses the best matching chunk (highest relevance score)
- Extracts key sentences
- Falls back to generic summary if needed

### 5. Warnings Generation
- Checks for extended stays (>90 days)
- Detects restriction keywords in chunks
- Always includes disclaimer

## Testing

Run the test script:

```bash
cd services/kg_service
python test_visa_policy_api.py
```

Or use curl:

```bash
curl -X POST http://localhost:8000/graphrag/visa-policy \
  -H "Content-Type: application/json" \
  -d @test_request.json
```

## Key Differences from LLM-based Query

| Feature | LLM Query (`/query`) | Visa Policy Query (`/visa-policy`) |
|---------|---------------------|-------------------------------------|
| LLM Usage | ✅ Yes (generates answer) | ❌ No (retrieval only) |
| Input Format | Simple question string | Structured JSON request |
| Output Format | Free-form text answer | Structured rules & evidence |
| Top-K Chunks | 5 (default) | 10 |
| Min Score | 0.5 | 0.4 (broader matching) |
| Response Time | Slower (LLM call) | Faster (no LLM) |
| Use Case | End-user Q&A | Data retrieval for downstream processing |

## Use Cases

1. **Service-to-Service Communication**: Another service (your friend's) handles the final answer generation
2. **Multi-step Processing**: Retrieve raw data first, then process/synthesize later
3. **Cost Optimization**: Avoid LLM costs when only data retrieval is needed
4. **Faster Response**: Skip LLM inference time
5. **Structured Output**: Need machine-readable rules instead of natural language

## Notes

- This endpoint does **NOT** use an LLM, so no OpenAI/Groq API key is required for queries
- The embedding model is still used for vector similarity search
- Answer finalization and synthesis should be done by the consuming service
- Always verify with official immigration sources before making travel decisions
