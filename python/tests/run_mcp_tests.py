#!/usr/bin/env python3
"""
MCP Tool Test Runner

Runs all MCP tool tests and generates a comprehensive report.
Use this script to validate MCP tool functionality after changes.
"""
import subprocess
import sys
import time
from pathlib import Path

def run_tests():
    """Run all MCP tool tests and display results"""
    print("🧪 Starting Archon MCP Tool Test Suite")
    print("=" * 50)
    
    start_time = time.time()
    
    # Test categories to run
    test_categories = [
        ("System Management", "test_health_check"),
        ("Knowledge Management", "test_get_available_sources test_crawl_single_page test_smart_crawl_url test_perform_rag_query test_search_code_examples test_upload_document"),
        ("Project Management", "test_list_projects test_get_project test_create_project test_delete_project"),
        ("Task Management", "test_list_tasks_by_project test_create_task test_get_task test_update_task_status test_update_task test_get_task_subtasks test_get_tasks_by_status test_delete_task"),
        ("Document Management", "test_add_project_document test_list_project_documents test_get_project_document test_update_project_document test_delete_project_document test_delete_source_tool"),
        ("Integration Tests", "test_full_workflow"),
        ("Error Handling", "test_error_handling"),
        ("Performance Tests", "test_tool_response_times")
    ]
    
    total_passed = 0
    total_failed = 0
    category_results = []
    
    for category_name, test_names in test_categories:
        print(f"\n🔍 Testing {category_name}...")
        print("-" * 30)
        
        # Run tests for this category using uv run
        cmd = [
            "uv", "run", "python", "-m", "pytest", 
            "test_mcp_tools.py",
            "-v",
            "--tb=short",
            "--no-header"
        ]
        
        # Add specific test filters
        for test_name in test_names.split():
            cmd.extend(["-k", test_name])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
            
            # Parse results
            output_lines = result.stdout.split('\n')
            passed = len([line for line in output_lines if "PASSED" in line])
            failed = len([line for line in output_lines if "FAILED" in line])
            
            total_passed += passed
            total_failed += failed
            
            category_results.append({
                "category": category_name,
                "passed": passed,
                "failed": failed,
                "output": result.stdout,
                "errors": result.stderr
            })
            
            # Display immediate results
            if failed == 0:
                print(f"✅ {category_name}: {passed} tests passed")
            else:
                print(f"❌ {category_name}: {passed} passed, {failed} failed")
                if result.stderr:
                    print(f"   Errors: {result.stderr[:200]}...")
            
        except Exception as e:
            print(f"❌ Error running {category_name} tests: {e}")
            category_results.append({
                "category": category_name,
                "passed": 0,
                "failed": 1,
                "output": "",
                "errors": str(e)
            })
            total_failed += 1
    
    # Generate final report
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "=" * 50)
    print("📊 FINAL TEST RESULTS")
    print("=" * 50)
    
    print(f"⏱️  Total Duration: {duration:.2f} seconds")
    print(f"✅ Tests Passed: {total_passed}")
    print(f"❌ Tests Failed: {total_failed}")
    print(f"📈 Success Rate: {(total_passed/(total_passed+total_failed)*100) if (total_passed+total_failed) > 0 else 0:.1f}%")
    
    print("\n📋 Category Breakdown:")
    for result in category_results:
        status = "✅" if result["failed"] == 0 else "❌"
        print(f"  {status} {result['category']}: {result['passed']} passed, {result['failed']} failed")
    
    # Show failures in detail if any
    if total_failed > 0:
        print("\n🔍 FAILURE DETAILS:")
        print("-" * 50)
        for result in category_results:
            if result["failed"] > 0:
                print(f"\n❌ {result['category']} Failures:")
                if result["errors"]:
                    print(f"   {result['errors']}")
                # Show relevant output lines
                failure_lines = [line for line in result["output"].split('\n') 
                               if "FAILED" in line or "ERROR" in line]
                for line in failure_lines[:3]:  # Show first 3 failure lines
                    print(f"   {line}")
    
    print("\n🎯 RECOMMENDATIONS:")
    if total_failed == 0:
        print("🎉 All tests passed! MCP tools are working correctly.")
        print("💡 Consider running performance benchmarks next.")
    else:
        print("🔧 Some tests failed. Check the details above.")
        print("💡 Run individual tests with: pytest test_mcp_tools.py::test_name -v")
        print("💡 Check MCP server logs for more details.")
    
    return total_failed == 0

def run_specific_test(test_name):
    """Run a specific test by name"""
    print(f"🧪 Running specific test: {test_name}")
    
    cmd = [
        "uv", "run", "python", "-m", "pytest", 
        f"test_mcp_tools.py::{test_name}",
        "-v", "-s"
    ]
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode == 0

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Run all tests
        success = run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 