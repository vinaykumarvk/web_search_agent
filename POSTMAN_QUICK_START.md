# Postman Quick Start Guide

## Step-by-Step Instructions

### Step 1: Start the API Server

Open a terminal and run:

```bash
cd /Users/n15318/web_search_agent
python run_server.py
```

You should see:
```
✅ OpenAI API key configured (.env file) - Real API calls enabled
🚀 Starting server on http://0.0.0.0:8000
   API docs: http://localhost:8000/docs
```

**Keep this terminal open** - the server needs to keep running.

---

### Step 2: Open Postman

1. Open Postman application
2. If you don't have Postman, download it from: https://www.postman.com/downloads/

---

### Step 3: Import the Collection

1. In Postman, click the **Import** button (top left)
2. Click **Upload Files**
3. Navigate to `/Users/n15318/web_search_agent/`
4. Select `Web_Research_Agent_API.postman_collection.json`
5. Click **Import**

You should now see a collection called **"Web Research Agent API"** in your sidebar.

---

### Step 4: Set Up Environment (Optional but Recommended)

1. Click the **Environments** icon (left sidebar, looks like an eye)
2. Click **+** to create a new environment
3. Name it: `Web Research Agent Local`
4. Add these variables:
   - `base_url` = `http://localhost:8000`
   - `task_id` = (leave empty for now)
5. Click **Save**
6. Select this environment from the dropdown (top right)

---

### Step 5: Test the API

#### Test 1: Health Check

1. Expand **"Web Research Agent API"** collection
2. Click **"Health Check"**
3. Click **Send** button (blue button, top right)
4. You should see:
   ```json
   {
     "status": "ok"
   }
   ```

✅ **If this works, your server is running!**

---

#### Test 2: Readiness Check (VERIFY API KEY)

1. Click **"Readiness Check (Verify OpenAI API Key)"**
2. Click **Send**
3. Check the response:
   - ✅ **Good**: `"openai_api_key_configured": true` → Real API calls enabled
   - ❌ **Bad**: `"openai_api_key_configured": false` → Add API key to `.env` file

---

#### Test 3: Quick Research

1. Click **"Quick Research (Synchronous)"**
2. Click **Send**
3. Wait for response (should take 10-30 seconds)
4. You should see a full research response with:
   - `envelope` - Contains the research report
   - `quality` - Quality report
   - `citations` - List of sources
   - `findings` - Research findings
   - `evidence` - Supporting evidence

---

#### Test 4: Deep Research (Async)

1. Click **"Deep Research (Asynchronous)"**
2. Click **Send**
3. You'll get a response with `task_id`:
   ```json
   {
     "task_id": "some-uuid-here",
     "status": "queued"
   }
   ```
4. **Copy the `task_id`** from the response
5. Set it in your environment:
   - Click **Environments** → Select your environment
   - Edit `task_id` variable → Paste the UUID
   - Save
6. Click **"Get Task Status"** → **Send**
7. Keep clicking **Send** until `status` is `"completed"`
8. You'll see the full research results

---

## All 8 Test Scenarios

The collection includes these pre-configured requests:

1. **Health Check** - Verify server is running
2. **Readiness Check** - Verify OpenAI API key is configured
3. **Quick Research** - Fast synchronous research
4. **Standard Research** - Moderate depth synchronous research
5. **Deep Research** - Long-running async research
6. **BRD Research** - Business Requirements Document
7. **JSON Output Format** - Request JSON instead of markdown
8. **Get Task Status** - Poll async task results

---

## Tips

### Viewing Responses

- **Pretty View**: Click the response body → Select **Pretty** tab
- **Raw View**: See raw JSON
- **Save Response**: Click **Save Response** button

### Modifying Requests

- Click any request to edit it
- Modify the JSON body in the **Body** tab
- Change the query, depth, purpose, etc.
- Click **Send** to test

### Using Variables

- Use `{{base_url}}` in URLs (automatically replaced)
- Use `{{task_id}}` after async requests
- Variables are shown in orange in Postman

### Testing Different Queries

Edit the request body to test different queries:

```json
{
  "query": "Your custom query here",
  "controls": {
    "depth": "quick",
    "purpose": "market_query"
  }
}
```

---

## Troubleshooting

### "Could not get response"
- ✅ Check server is running (Step 1)
- ✅ Check `base_url` is `http://localhost:8000`
- ✅ Try Health Check first

### "openai_api_key_configured: false"
- ✅ Open `.env` file
- ✅ Add: `OPENAI_API_KEY=your-key-here`
- ✅ Restart server

### "Task not found"
- ✅ Copy `task_id` from async response
- ✅ Set it in environment variables
- ✅ Use the exact task_id in "Get Task Status"

### Server won't start
- ✅ Check port 8000 is free: `lsof -i:8000`
- ✅ Use different port: `python run_server.py 8001`
- ✅ Update `base_url` to match port

---

## Expected Response Times

- **Health Check**: < 1 second
- **Quick Research**: 10-30 seconds
- **Standard Research**: 30-60 seconds
- **Deep Research**: 2-5 minutes (async)

---

## Next Steps

1. ✅ Test all 8 scenarios
2. ✅ Try modifying queries
3. ✅ Test different depths (quick/standard/deep)
4. ✅ Test different purposes (brd, company_research, etc.)
5. ✅ Check server logs for detailed API call information

Happy testing! 🚀

