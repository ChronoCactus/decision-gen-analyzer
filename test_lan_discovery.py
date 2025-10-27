"""
Simple test to verify LAN discovery configuration endpoint.
Run this after starting the backend to test the /api/v1/config endpoint.
"""

import requests
import sys


def test_config_endpoint(base_url="http://localhost:8000"):
    """Test the configuration endpoint."""
    print(f"Testing configuration endpoint at {base_url}/api/v1/config")
    print("=" * 60)
    
    try:
        response = requests.get(f"{base_url}/api/v1/config", timeout=5)
        response.raise_for_status()
        
        config = response.json()
        print("✅ Config endpoint is working!")
        print(f"\nConfiguration:")
        print(f"  - API Base URL: {config.get('api_base_url')}")
        print(f"  - LAN Discovery Enabled: {config.get('lan_discovery_enabled')}")
        
        if config.get('lan_discovery_enabled'):
            print("\n🌐 LAN Discovery is ENABLED")
            print(f"   Frontend will use: {config.get('api_base_url')}")
            print(f"   Access frontend from any device on your network")
        else:
            print("\n🔒 LAN Discovery is DISABLED")
            print(f"   Frontend will use: {config.get('api_base_url')}")
            print(f"   Only accessible via localhost")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Failed to connect to backend")
        print("   Make sure the backend is running on port 8000")
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        print("   Backend might be overloaded or not responding")
        return False
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_health_endpoint(base_url="http://localhost:8000"):
    """Test the health endpoint."""
    print(f"\nTesting health endpoint at {base_url}/health")
    print("=" * 60)
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        
        health = response.json()
        print("✅ Health endpoint is working!")
        print(f"  - Status: {health.get('status')}")
        print(f"  - Service: {health.get('service')}")
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Decision Analyzer - LAN Discovery Test")
    print("=" * 60 + "\n")
    
    # Allow custom base URL as command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    health_ok = test_health_endpoint(base_url)
    config_ok = test_config_endpoint(base_url)
    
    print("\n" + "=" * 60)
    if health_ok and config_ok:
        print("✅ All tests passed!")
        print("\nNext steps:")
        print("  1. If LAN discovery is disabled, set environment variables:")
        print("     ENABLE_LAN_DISCOVERY=true")
        print("     HOST_IP=<your-ip-address>")
        print("  2. Restart the backend")
        print("  3. Run this test again to verify")
    else:
        print("❌ Some tests failed")
        print("\nTroubleshooting:")
        print("  - Ensure backend is running: docker-compose up backend")
        print("  - Check backend logs: docker-compose logs backend")
        print("  - Verify port 8000 is not blocked by firewall")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
