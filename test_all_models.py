#!/usr/bin/env python3
"""Test all OpenAI models used by the Web Research Agent."""
import os
import sys
import time
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("❌ ERROR: OPENAI_API_KEY not found!")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("❌ ERROR: OpenAI package not installed")
    sys.exit(1)

client = OpenAI(api_key=api_key)

print("=" * 80)
print("TESTING ALL OPENAI MODELS")
print("=" * 80)
print()

results = {}

# Test 1: GPT-5-mini (Router/Clarifier)
print("Test 1: GPT-5-mini (Router/Clarifier)")
print("-" * 80)
try:
    start_time = time.time()
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Classify this query: 'What is artificial intelligence?' Return JSON with purpose and depth."}
        ],
        max_completion_tokens=100,
        response_format={"type": "json_object"},
    )
    elapsed = time.time() - start_time
    result = response.choices[0].message.content
    tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
    
    print(f"   ✅ SUCCESS")
    print(f"   Response: {result[:100]}...")
    print(f"   Tokens: {tokens}")
    print(f"   Latency: {elapsed:.2f}s")
    results["gpt-5-mini"] = {"status": "success", "latency": elapsed, "tokens": tokens}
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    results["gpt-5-mini"] = {"status": "failed", "error": str(e)}

print()

# Test 2: GPT-5.1 (Writer/Fact Checker/Researcher)
print("Test 2: GPT-5.1 (Writer/Fact Checker/Researcher)")
print("-" * 80)
try:
    start_time = time.time()
    # GPT-5.1 uses max_completion_tokens instead of max_tokens
    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[
            {"role": "system", "content": "You are an expert research writer."},
            {"role": "user", "content": "Write a brief summary (2-3 sentences) about artificial intelligence."}
        ],
        max_completion_tokens=100,
        temperature=0.3,
    )
    elapsed = time.time() - start_time
    result = response.choices[0].message.content
    tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
    
    print(f"   ✅ SUCCESS")
    print(f"   Response: {result}")
    print(f"   Tokens: {tokens}")
    print(f"   Latency: {elapsed:.2f}s")
    results["gpt-5.1"] = {"status": "success", "latency": elapsed, "tokens": tokens}
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    results["gpt-5.1"] = {"status": "failed", "error": str(e)}

print()

# Test 3: O3-deep-research (Deep Research)
print("Test 3: O3-deep-research (Deep Research)")
print("-" * 80)
try:
    start_time = time.time()
    
    # O3-deep-research uses Responses API - check how we use it in the codebase
    # Based on app/tools/deep_research.py, we use responses.create() for background mode
    # For testing, we'll use a simple synchronous call
    
    print("   Testing with Responses API (background mode)...")
    
    # Start background research (like we do in the app)
    # Note: The actual API may not support response_mode parameter
    # Based on codebase, we use responses.create() which defaults to background mode
    response = client.responses.create(
        model="o3-deep-research",
        input="What is artificial intelligence? Provide a brief explanation.",
        tools=[{"type": "web_search"}],
    )
    
    response_id = getattr(response, "id", None) or getattr(response, "response_id", None)
    if not response_id:
        raise ValueError("No response_id returned")
    
    print(f"   Started background research: {response_id}")
    print("   Polling for completion (this may take 30-60 seconds)...")
    
    # Poll for completion (like we do in the app)
    max_wait = 120  # 2 minutes max for test
    poll_start = time.time()
    while time.time() - poll_start < max_wait:
        status_response = client.responses.retrieve(response_id)
        status = getattr(status_response, "status", None) or getattr(status_response, "response_status", None)
        
        if status in ("completed", "succeeded"):
            elapsed = time.time() - start_time
            tokens = getattr(status_response, "usage", None)
            token_count = tokens.total_tokens if tokens and hasattr(tokens, 'total_tokens') else 0
            
            # Extract output
            output_text = getattr(status_response, "output_text", None)
            if not output_text:
                output = getattr(status_response, "output", None)
                if output:
                    text_parts = []
                    for item in output:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        elif hasattr(item, 'type') and getattr(item, 'type') == 'text':
                            text_parts.append(getattr(item, 'text', ''))
                    output_text = ' '.join(text_parts)
            
            print(f"   ✅ SUCCESS")
            print(f"   Response: {output_text[:200] if output_text else 'Research completed'}...")
            print(f"   Tokens: {token_count}")
            print(f"   Latency: {elapsed:.2f}s")
            results["o3-deep-research"] = {"status": "success", "latency": elapsed, "tokens": token_count}
            break
        elif status in ("failed", "error"):
            error_msg = getattr(status_response, "error", {}).get("message", "Unknown error") if hasattr(status_response, "error") else "Unknown error"
            raise RuntimeError(f"Deep research failed: {error_msg}")
        
        time.sleep(2)  # Poll every 2 seconds
    else:
        raise TimeoutError("Deep research did not complete within timeout")
        
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    print(f"   Error type: {type(e).__name__}")
    import traceback
    print(f"   Details: {traceback.format_exc()}")
    results["o3-deep-research"] = {"status": "failed", "error": str(e)}

print()
print("=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print()

all_success = all(r.get("status") == "success" for r in results.values())

for model, result in results.items():
    status_icon = "✅" if result["status"] == "success" else "❌"
    print(f"{status_icon} {model:20s}: ", end="")
    if result["status"] == "success":
        latency = result.get("latency", 0)
        tokens = result.get("tokens", 0)
        print(f"SUCCESS (Latency: {latency:.2f}s, Tokens: {tokens})")
    else:
        print(f"FAILED - {result.get('error', 'Unknown error')}")

print()
print("=" * 80)
if all_success:
    print("✅ ALL MODELS ARE ACCESSIBLE AND WORKING")
    print("=" * 80)
    print()
    print("Your Web Research Agent will use:")
    print("  - GPT-5-mini: Router & Clarifier agents")
    print("  - GPT-5.1: Writer, Fact Checker, and Researcher agents")
    print("  - O3-deep-research: Deep research tasks")
    print()
    print("All models are ready for Postman testing!")
else:
    print("⚠️  SOME MODELS FAILED")
    print("=" * 80)
    print()
    print("Check the errors above and verify:")
    print("  - API key has access to all models")
    print("  - Models are available in your region")
    print("  - Network connectivity is working")
    sys.exit(1)

