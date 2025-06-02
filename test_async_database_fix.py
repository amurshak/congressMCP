#!/usr/bin/env python3
"""
Test the async database fix with production credentials
"""
import os
import asyncio
import sys
import time

# Add the CongressionalMCP directory to the path
sys.path.append('/Users/alexmurshak/Coding/MCP/CongressMcpFiles/CongressionalMCP')

from congress_api.core.database import db_client
from congress_api.core.auth import check_rate_limit, db_validate_api_key

async def test_database_operations():
    """Test the async database operations that were causing timeouts"""
    
    print("🧪 Testing Async Database Operations...")
    
    # Test 1: API Key Validation (this calls database)
    print("\n1. Testing API key validation...")
    api_key = "lawgiver_pro_e5dcc776_mNB8q8KabgKYJaqQPoKLRg"  # Known working key
    
    start_time = time.time()
    try:
        user_info = await db_validate_api_key(api_key)
        end_time = time.time()
        
        if user_info:
            print(f"   ✅ API key validation SUCCESS - {end_time - start_time:.2f}s")
            print(f"   User: {user_info['email']}, Tier: {user_info['tier']}")
            
            # Test 2: Rate Limiting (this calls track_usage and get_daily_usage)
            print("\n2. Testing rate limiting...")
            start_time = time.time()
            
            try:
                await check_rate_limit(user_info["user_id"], user_info["tier"])
                end_time = time.time()
                print(f"   ✅ Rate limiting check SUCCESS - {end_time - start_time:.2f}s")
                
                # Test 3: Multiple concurrent operations
                print("\n3. Testing concurrent database operations...")
                start_time = time.time()
                
                tasks = []
                for i in range(5):
                    task = check_rate_limit(user_info["user_id"], user_info["tier"])
                    tasks.append(task)
                
                await asyncio.gather(*tasks)
                end_time = time.time()
                print(f"   ✅ Concurrent operations SUCCESS - {end_time - start_time:.2f}s")
                
            except Exception as rate_error:
                end_time = time.time()
                print(f"   ❌ Rate limiting FAILED - {end_time - start_time:.2f}s")
                print(f"   Error: {rate_error}")
                
        else:
            end_time = time.time()
            print(f"   ❌ API key validation FAILED - {end_time - start_time:.2f}s")
            
    except Exception as e:
        end_time = time.time()
        print(f"   ❌ API key validation ERROR - {end_time - start_time:.2f}s")
        print(f"   Error: {e}")

async def test_thread_pool_saturation():
    """Test if our thread pool approach can handle multiple simultaneous requests"""
    print("\n🔄 Testing Thread Pool Saturation...")
    
    api_key = "lawgiver_pro_e5dcc776_mNB8q8KabgKYJaqQPoKLRg"
    
    async def simulate_request():
        """Simulate a full middleware request"""
        user_info = await db_validate_api_key(api_key)
        if user_info:
            await check_rate_limit(user_info["user_id"], user_info["tier"])
        return user_info is not None
    
    # Simulate 10 concurrent requests (like production load)
    start_time = time.time()
    tasks = [simulate_request() for _ in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    
    success_count = sum(1 for r in results if r is True)
    error_count = sum(1 for r in results if isinstance(r, Exception))
    
    print(f"   Results: {success_count} success, {error_count} errors")
    print(f"   Total time: {end_time - start_time:.2f}s")
    print(f"   Average per request: {(end_time - start_time) / 10:.2f}s")
    
    if error_count > 0:
        print("   Errors encountered:")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"     Request {i}: {result}")

if __name__ == "__main__":
    asyncio.run(test_database_operations())
    asyncio.run(test_thread_pool_saturation())
