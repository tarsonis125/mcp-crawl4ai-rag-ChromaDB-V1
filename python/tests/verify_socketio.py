#!/usr/bin/env python3
"""
Quick verification script for Socket.IO implementation.
Run this to verify that Socket.IO is properly integrated.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def verify_imports():
    """Verify all imports work correctly."""
    print("Verifying imports...")
    
    try:
        from src.server.socketio_app import get_socketio_instance, NAMESPACE_CRAWL
        print("✓ socketio_app imports OK")
        
        from src.server.socketio.crawl_namespace import CrawlNamespace
        print("✓ CrawlNamespace import OK")
        
        from src.server.socketio.progress_utils import (
            start_crawl_progress,
            update_crawl_progress,
            complete_crawl_progress,
            error_crawl_progress,
            get_active_crawl
        )
        print("✓ progress_utils imports OK")
        
        from src.server.fastapi.knowledge_api import router
        print("✓ knowledge_api import OK")
        
        # Check Socket.IO instance
        sio = get_socketio_instance()
        print(f"✓ Socket.IO instance created: {sio}")
        
        # Check namespace constant
        print(f"✓ NAMESPACE_CRAWL: {NAMESPACE_CRAWL}")
        
        return True
        
    except Exception as e:
        print(f"✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def verify_namespace_registration():
    """Verify namespace is properly registered."""
    print("\nVerifying namespace registration...")
    
    try:
        from src.server.socketio_app import get_socketio_instance
        from src.server.socketio.crawl_namespace import CrawlNamespace
        
        sio = get_socketio_instance()
        
        # Check if namespace can be instantiated
        namespace = CrawlNamespace('/crawl')
        print(f"✓ CrawlNamespace instantiated: {namespace}")
        
        # Test progress tracking
        from src.server.socketio.progress_utils import start_crawl_progress, get_active_crawl
        
        test_progress_id = "test-123"
        await start_crawl_progress(test_progress_id, {
            'currentUrl': 'https://test.com',
            'status': 'starting',
            'percentage': 0
        })
        
        active_crawl = get_active_crawl(test_progress_id)
        if active_crawl:
            print(f"✓ Progress tracking works: {active_crawl['status']}")
        else:
            print("✗ Progress tracking failed")
            
        return True
        
    except Exception as e:
        print(f"✗ Namespace error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Socket.IO Implementation Verification")
    print("=" * 60)
    
    all_ok = True
    
    # Test 1: Imports
    if not await verify_imports():
        all_ok = False
    
    # Test 2: Namespace registration
    if not await verify_namespace_registration():
        all_ok = False
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ All verifications passed!")
    else:
        print("❌ Some verifications failed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())