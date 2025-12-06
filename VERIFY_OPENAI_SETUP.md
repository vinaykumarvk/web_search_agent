# Verifying OpenAI API Integration

## ⚠️ Important: Real API Calls Require OpenAI API Key

The Web Research Agent **will make real OpenAI API calls** when `OPENAI_API_KEY` is set. Without it, the API uses fallbacks/mocks.

## Quick Verification

### 1. Check API Key is Configured

**Option A: Check .env file**
```bash
cat .env | grep OPENAI_API_KEY
```

**Option B: Check environment variable**
```bash
echo $OPENAI_API_KEY
```

Should show your API key (not empty).

### 2. Start Server and Check Readiness

```bash
python run_server.py
```

Look for:
- ✅ `OpenAI API key configured - Real API calls enabled`
- ❌ `WARNING: OPENAI_API_KEY not set!` (means fallbacks will be used)

### 3. Test Readiness Endpoint

```bash
curl http://localhost:8000/health/ready
```

**Expected Response (API Key Set):**
```json
{
  "status": "ready",
  "openai_api_key_configured": true,
  "message": "API will make real OpenAI calls",
  "endpoints_available": {
    "router": "LLM-based",
    "clarifier": "LLM-based",
    "researcher": "OpenAI Responses API",
    "writer": "GPT-5.1",
    "fact_checker": "GPT-5.1 + Heuristics",
    "deep_research": "O3-deep-research"
  }
}
```

**If API Key Missing:**
```json
{
  "status": "degraded",
  "openai_api_key_configured": false,
  "message": "WARNING: OPENAI_API_KEY not set - API will use fallbacks/mocks",
  "endpoints_available": {
    "router": "Heuristic fallback",
    "researcher": "No-op (empty results)",
    "writer": "Placeholder content",
    ...
  }
}
```

## What Each Endpoint Does

### With OpenAI API Key (Real Calls):

1. **Router** (`LLMRouterAgent`)
   - Uses **GPT-5-mini** to classify query intent
   - Determines purpose, depth, clarification needs
   - Makes real OpenAI API call

2. **Clarifier** (`LLMClarifierAgent`)
   - Uses **GPT-5-mini** to generate clarification questions
   - Makes real OpenAI API call

3. **Researcher** (`WebSearchTool`)
   - Uses **OpenAI Responses API** with `web_search` tool
   - Uses **GPT-5.1** for search queries
   - Makes real OpenAI API calls

4. **Deep Research** (`DeepResearchClient`)
   - Uses **O3-deep-research** model
   - Makes real OpenAI API calls
   - Performs autonomous multi-hop web search

5. **Writer** (`GPT5WriterAgent`)
   - Uses **GPT-5.1** to generate structured deliverables
   - Makes real OpenAI API calls
   - Generates full research reports

6. **Fact Checker** (`LLMFactCheckerAgent`)
   - Uses **GPT-5.1** for quality analysis
   - Uses **SemanticCitationValidator** (GPT-5.1) for citation validation
   - Makes real OpenAI API calls

### Without OpenAI API Key (Fallbacks):

1. **Router**: Heuristic keyword-based routing
2. **Clarifier**: Skipped (returns original query)
3. **Researcher**: Returns empty results
4. **Deep Research**: Returns mock test data
5. **Writer**: Returns placeholder content
6. **Fact Checker**: Uses heuristics only

## Testing Real API Calls

### Postman Workflow:

1. **Set API Key**:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **Start Server**:
   ```bash
   python run_server.py
   ```

3. **Verify Readiness** (in Postman):
   - Run **Readiness Check** request
   - Confirm `openai_api_key_configured: true`

4. **Test Research**:
   - Run **Quick Research** request
   - Should return real research results with citations
   - Check response includes actual content (not placeholders)

5. **Verify Real Calls**:
   - Check server logs for OpenAI API calls
   - Response should have real citations and content
   - Quality report should be generated

## Expected Behavior

### With API Key:
- ✅ Real web search results
- ✅ GPT-5.1 generated content
- ✅ Actual citations from web sources
- ✅ Quality reports with real analysis
- ✅ Deep research with O3-deep-research

### Without API Key:
- ❌ Empty search results
- ❌ Placeholder content
- ❌ No real citations
- ❌ Heuristic-only quality checks
- ❌ Mock deep research data

## Cost Considerations

Real API calls will consume OpenAI API credits:
- **Router**: ~$0.001 per request (GPT-5-mini)
- **Clarifier**: ~$0.001 per request (GPT-5-mini)
- **Researcher**: ~$0.01-0.05 per search (GPT-5.1 + Responses API)
- **Writer**: ~$0.05-0.20 per request (GPT-5.1)
- **Fact Checker**: ~$0.02-0.10 per request (GPT-5.1)
- **Deep Research**: ~$0.50-2.00 per request (O3-deep-research)

**Total per research request**: ~$0.10-2.50 depending on depth

## Troubleshooting

**API returns placeholder content:**
- Check `OPENAI_API_KEY` is set: `echo $OPENAI_API_KEY`
- Verify readiness endpoint shows `openai_api_key_configured: true`
- Check server logs for API errors

**API returns empty results:**
- Verify API key has credits
- Check OpenAI API status
- Review server logs for error messages

**API calls fail:**
- Verify API key is valid
- Check network connectivity
- Review error messages in server logs

