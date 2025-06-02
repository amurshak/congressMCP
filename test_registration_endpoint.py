#!/usr/bin/env python3
"""
Test script for the new registration endpoint
"""
import asyncio
import httpx
import json
import sys

async def test_registration_endpoint():
    """Test the /api/register/free endpoint"""
    
    # Test data
    test_email = "test@example.com"
    base_url = "http://localhost:8000"  # Local development server
    endpoint = f"{base_url}/api/register/free"
    
    print(f"Testing registration endpoint: {endpoint}")
    print(f"Test email: {test_email}")
    
    payload = {"email": test_email}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint, 
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            try:
                response_data = response.json()
                print(f"Response Body: {json.dumps(response_data, indent=2)}")
            except:
                print(f"Response Body (raw): {response.text}")
                
            if response.status_code == 200:
                print("✅ Registration endpoint test PASSED!")
            else:
                print("❌ Registration endpoint test FAILED!")
                
    except Exception as e:
        print(f"❌ Error testing registration endpoint: {e}")

async def test_health_endpoint():
    """Test the /api/health endpoint"""
    
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/health"
    
    print(f"\nTesting health endpoint: {endpoint}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint)
            
            print(f"Health Response Status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                print(f"Health Response: {json.dumps(response_data, indent=2)}")
                print("✅ Health endpoint test PASSED!")
            else:
                print(f"❌ Health endpoint test FAILED! Status: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")

if __name__ == "__main__":
    print("🧪 Testing Congressional MCP Registration Endpoints")
    print("=" * 50)
    
    # Run the tests
    asyncio.run(test_health_endpoint())
    asyncio.run(test_registration_endpoint())
    
    print("\n" + "=" * 50)
    print("Test completed!")
