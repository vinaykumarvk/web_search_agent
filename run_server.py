#!/usr/bin/env python3
"""Start the Web Research Agent API server."""
import os
import sys
from pathlib import Path
import uvicorn
from app.config import load_settings, DEFAULT_ENV_FILE

def check_api_key():
    """Check if OpenAI API key is configured."""
    settings = load_settings()
    
    # Check if .env file exists
    env_file_exists = DEFAULT_ENV_FILE.exists()
    
    if not settings.openai_api_key:
        print("=" * 80)
        print("⚠️  WARNING: OPENAI_API_KEY not configured!")
        print("=" * 80)
        print()
        
        if not env_file_exists:
            print("No .env file found. Creating .env.example for reference...")
            print()
            print("To configure your API key, create a .env file:")
            print("  1. Copy .env.example to .env:")
            print("     cp .env.example .env")
            print()
            print("  2. Edit .env and add your OpenAI API key:")
            print("     OPENAI_API_KEY=your-api-key-here")
            print()
        else:
            print(".env file exists but OPENAI_API_KEY is not set.")
            print("Please add OPENAI_API_KEY to your .env file:")
            print("  OPENAI_API_KEY=your-api-key-here")
            print()
        
        print("Alternative: Set environment variable:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        print()
        print("The API will run but will use fallbacks/mocks instead of real OpenAI calls:")
        print("  - Router: Heuristic fallback (not LLM-based)")
        print("  - Clarifier: Skipped")
        print("  - Researcher: No-op (empty search results)")
        print("  - Writer: Placeholder content (not GPT-5.1)")
        print("  - Fact Checker: Heuristics only")
        print("  - Deep Research: Mock data")
        print()
        print("Check readiness: GET http://localhost:8000/health/ready")
        print("=" * 80)
        print()
    else:
        source = "environment variable" if os.environ.get("OPENAI_API_KEY") else ".env file"
        print("=" * 80)
        print(f"✅ OpenAI API key configured ({source}) - Real API calls enabled")
        print("=" * 80)
        print()

if __name__ == "__main__":
    import sys
    
    check_api_key()
    
    # Allow port override via environment variable or command line
    port = int(os.environ.get("PORT", 8000))
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}. Using default port 8000.")
            port = 8000
    
    # Check if port is available
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    
    if result == 0:
        print(f"⚠️  Port {port} is already in use!")
        print(f"   Options:")
        print(f"   1. Kill existing process: lsof -ti:{port} | xargs kill -9")
        print(f"   2. Use different port: python run_server.py 8001")
        print(f"   3. Set PORT env var: PORT=8001 python run_server.py")
        sys.exit(1)
    
    print(f"🚀 Starting server on http://0.0.0.0:{port}")
    print(f"   API docs: http://localhost:{port}/docs")
    print()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )

