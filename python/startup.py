#!/usr/bin/env python3
"""
Startup script for MCP Crawl4AI RAG UI application.
Sets up the environment and guides through initial configuration.
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path
from src.server.services.credential_service import credential_service

def print_header():
    """Print startup header."""
    print("=" * 60)
    print("🚀 MCP Crawl4AI RAG UI - Startup Script")
    print("=" * 60)
    print()

def check_env_file():
    """Check if .env file exists and has required Supabase configuration."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found!")
        print("📝 Please create a .env file based on .env-doc.md")
        print("   You only need to set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        print()
        return False
    
    # Check if required variables are set
    from dotenv import load_dotenv
    load_dotenv()
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing required Supabase configuration in .env!")
        print("   Required: SUPABASE_URL and SUPABASE_SERVICE_KEY")
        print("   See .env-doc.md for instructions")
        print()
        return False
    
    print("✅ Environment file configured correctly")
    return True

async def check_database_setup():
    """Check if the credentials table exists in Supabase."""
    try:
        # Try to initialize credentials - this will fail if table doesn't exist
        await credential_service.load_all_credentials()
        print("✅ Database credentials table found")
        return True
    except Exception as e:
        print(f"❌ Database setup incomplete: {e}")
        print("📝 Please run the initial_setup.sql file in your Supabase SQL editor")
        print("   This will create the settings table and initial data")
        print()
        return False

def install_dependencies():
    """Install Python dependencies."""
    print("📦 Installing Python dependencies...")
    try:
        result = subprocess.run(
            ["uv", "pip", "install", "--system", "-e", ".[api]"],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Python dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print("   Make sure you have uv installed: https://docs.astral.sh/uv/")
        return False
    except FileNotFoundError:
        print("❌ uv not found!")
        print("   Please install uv: https://docs.astral.sh/uv/")
        return False

def setup_frontend():
    """Setup React frontend dependencies."""
    print("🎨 Setting up React frontend...")
    frontend_path = Path("archon-ui-main")
    
    if not frontend_path.exists():
        print("❌ Frontend directory not found!")
        return False
    
    try:
        # Change to frontend directory and install dependencies
        result = subprocess.run(
            ["npm", "install"],
            cwd=frontend_path,
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Frontend dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install frontend dependencies: {e}")
        return False
    except FileNotFoundError:
        print("❌ npm not found!")
        print("   Please install Node.js: https://nodejs.org/")
        return False

def run_setup_sql():
    """Guide user through SQL setup."""
    print()
    print("📋 Database Setup Required:")
    print("   1. Open your Supabase dashboard")
    print("   2. Go to SQL Editor")
    print("   3. Copy and run the contents of 'initial_setup.sql'")
    print("   4. This will create the settings table with default settings")
    print()
    input("Press Enter when you've completed the SQL setup...")

async def start_services():
    """Start the backend and frontend services."""
    print()
    print("🚀 Starting services...")
    print("   Backend API will run on http://localhost:8080")
    print("   Frontend UI will run on http://localhost:3737")
    print()
    print("💡 Tip: You can now configure all other settings via the Settings page!")
    print("   - Add your OpenAI API key (encrypted)")
    print("   - Configure model choices")
    print("   - Enable RAG strategies")
    print()
    
    try:
        # Start using docker-compose
        print("🐳 Starting with Docker Compose...")
        result = subprocess.run(
            ["docker-compose", "up", "--build"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start with Docker: {e}")
        print("   Trying manual startup...")
        
        # Manual startup fallback
        print("🔧 Starting backend API server...")
        backend_process = subprocess.Popen([
            "python", "-m", "uvicorn", "src.main:app", 
            "--host", "0.0.0.0", "--port", "8080", "--reload"
        ])
        
        print("🎨 Starting frontend development server...")
        frontend_process = subprocess.Popen([
            "npm", "run", "dev"
        ], cwd="archon-ui-main")
        
        print("✅ Services started!")
        print("   Backend: http://localhost:8080")
        print("   Frontend: http://localhost:3737")
        print("   Press Ctrl+C to stop")
        
        try:
            # Wait for processes
            backend_process.wait()
        except KeyboardInterrupt:
            print("\n⏹️  Stopping services...")
            backend_process.terminate()
            frontend_process.terminate()

async def main():
    """Main startup routine."""
    print_header()
    
    # Step 1: Check environment file
    if not check_env_file():
        sys.exit(1)
    
    # Step 2: Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Step 3: Setup frontend
    if not setup_frontend():
        sys.exit(1)
    
    # Step 4: Check database setup
    if not await check_database_setup():
        run_setup_sql()
        
        # Re-check after user setup
        if not await check_database_setup():
            print("❌ Database setup still incomplete. Please check your SQL execution.")
            sys.exit(1)
    
    # Step 5: Start services
    await start_services()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Startup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Startup failed: {e}")
        sys.exit(1) 