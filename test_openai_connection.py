#!/usr/bin/env python3
"""Test OpenAI API connectivity and API key validity."""
import os
import sys
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        print("✅ Loaded .env file")
    else:
        print("⚠️  No .env file found, checking environment variables")
except ImportError:
    print("⚠️  python-dotenv not installed, checking environment variables only")

# Check API key
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("❌ ERROR: OPENAI_API_KEY not found!")
    print("   Set it in .env file or as environment variable")
    sys.exit(1)

print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
print()

# Test OpenAI API
try:
    from openai import OpenAI
    
    print("🔍 Testing OpenAI API connectivity...")
    print()
    
    client = OpenAI(api_key=api_key)
    
    # Test 1: Simple chat completion (cheapest test)
    print("Test 1: Chat Completion API...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cheapest model for testing
            messages=[
                {"role": "user", "content": "Say 'API connection successful' if you can read this."}
            ],
            max_tokens=10,
        )
        result = response.choices[0].message.content
        print(f"   ✅ Success: {result}")
        print(f"   Tokens used: {response.usage.total_tokens}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        sys.exit(1)
    
    print()
    
    # Test 2: Check if Responses API is available
    print("Test 2: Responses API availability...")
    try:
        # Just check if the client has responses attribute
        if hasattr(client, 'responses'):
            print("   ✅ Responses API available")
        else:
            print("   ⚠️  Responses API not available (may need SDK update)")
    except Exception as e:
        print(f"   ⚠️  Could not check Responses API: {e}")
    
    print()
    
    # Test 3: List models (verify API key permissions)
    print("Test 3: API Key permissions...")
    try:
        models = client.models.list()
        model_count = len(list(models))
        print(f"   ✅ API key has access to {model_count} models")
        
        # Check for specific models we use
        model_names = [model.id for model in models]
        required_models = ["gpt-4o-mini", "gpt-5-mini", "gpt-5.1", "o3-deep-research"]
        available = [m for m in required_models if any(m in name for name in model_names)]
        if available:
            print(f"   ✅ Found models: {', '.join(available)}")
        else:
            print(f"   ⚠️  Some required models may not be available")
    except Exception as e:
        print(f"   ⚠️  Could not list models: {e}")
    
    print()
    print("=" * 80)
    print("✅ OpenAI API Connection Test: SUCCESS")
    print("=" * 80)
    print()
    print("Your API key is valid and OpenAI API is reachable!")
    print("The Web Research Agent will make real API calls.")
    print()
    
except ImportError:
    print("❌ ERROR: OpenAI package not installed")
    print("   Install with: pip install openai")
    sys.exit(1)
except Exception as e:
    print("=" * 80)
    print("❌ OpenAI API Connection Test: FAILED")
    print("=" * 80)
    print()
    print(f"Error: {e}")
    print()
    print("Possible issues:")
    print("  1. Invalid API key")
    print("  2. Network connectivity issues")
    print("  3. OpenAI API service outage")
    print("  4. API key has insufficient permissions")
    print()
    sys.exit(1)

