#!/usr/bin/env python3
"""
Test runner for Amendments API functionality in CongressMCP.

This script runs comprehensive tests for all amendments-related features
and provides a detailed summary of results.
"""

import sys
import os
import time
from datetime import datetime

# Add the parent directory to the Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def run_amendments_tests():
    """Run all amendments tests and provide detailed output."""
    print("🚀 Starting Amendments API Tests...")
    print(f"📅 Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    try:
        # Import and run the test module
        from test_amendments_functionality import run_amendments_tests as run_tests
        
        start_time = time.time()
        results = run_tests()
        end_time = time.time()
        
        print("\n" + "=" * 70)
        print("🏁 AMENDMENTS API TEST RESULTS")
        print("=" * 70)
        
        # Display detailed results
        print(f"⏱️  Execution Time: {end_time - start_time:.2f} seconds")
        print(f"🧪 Total Tests: {results['tests_run']}")
        print(f"✅ Passed: {results['tests_run'] - results['failures'] - results['errors']}")
        print(f"❌ Failed: {results['failures']}")
        print(f"💥 Errors: {results['errors']}")
        
        # Overall status
        if results['success']:
            print("\n🎉 OVERALL STATUS: ALL TESTS PASSED! ✅")
            print("\n📋 Test Categories Verified:")
            print("   ✅ Amendment formatting functions")
            print("   ✅ Search patterns and keyword filtering")
            print("   ✅ API integration patterns")
            print("   ✅ Error handling and edge cases")
            
            print("\n🔧 Amendments API Features Tested:")
            print("   ✅ format_amendment_summary() - Brief amendment overviews")
            print("   ✅ format_amendment_details() - Detailed amendment information")
            print("   ✅ format_amendment_action() - Legislative action formatting")
            print("   ✅ Keyword search validation")
            print("   ✅ Amendment type validation (SAMDT, HAMDT)")
            print("   ✅ Congress number validation")
            print("   ✅ Missing data handling")
            print("   ✅ Invalid parameter detection")
            
            print("\n🎯 Production Readiness:")
            print("   ✅ All formatting functions handle missing data gracefully")
            print("   ✅ Search patterns support current and historical congresses")
            print("   ✅ Error handling prevents crashes with invalid inputs")
            print("   ✅ API integration follows Congressional MCP patterns")
            
        else:
            print(f"\n⚠️  OVERALL STATUS: {results['failures'] + results['errors']} TEST(S) FAILED ❌")
            print("\n🔍 Please review the detailed test output above to identify issues.")
            print("💡 Common issues to check:")
            print("   - Missing import dependencies")
            print("   - Incorrect function signatures")
            print("   - API response format changes")
            print("   - Invalid test data assumptions")
        
        print("\n" + "=" * 70)
        
        return results['success']
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure you're running from the CongressMCP/tests/ directory")
        print("💡 Verify all required modules are available")
        return False
        
    except Exception as e:
        print(f"💥 Unexpected Error: {e}")
        print("💡 Check the test file for syntax errors or missing dependencies")
        return False

def main():
    """Main function to run amendments tests."""
    print("🏛️  CONGRESSIONAL MCP - AMENDMENTS API TEST SUITE")
    print("=" * 70)
    print("📝 Testing all amendments-related functionality...")
    print("🔍 Validating formatting, search patterns, and error handling")
    print()
    
    success = run_amendments_tests()
    
    if success:
        print("\n🎊 Amendments API testing completed successfully!")
        print("🚀 All amendments functionality is ready for production use.")
        exit_code = 0
    else:
        print("\n🚨 Amendments API testing failed!")
        print("🔧 Please fix the issues before deploying amendments functionality.")
        exit_code = 1
    
    print("\n📚 Next Steps:")
    if success:
        print("   1. ✅ Amendments API is fully tested and functional")
        print("   2. 🧪 Consider testing other Congressional MCP features")
        print("   3. 📊 Run integration tests with production API")
        print("   4. 🚀 Deploy with confidence!")
    else:
        print("   1. 🔍 Review test failures and fix underlying issues")
        print("   2. 🧪 Re-run tests after making corrections")
        print("   3. 📝 Update test cases if API behavior has changed")
        print("   4. 🔄 Repeat until all tests pass")
    
    return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
