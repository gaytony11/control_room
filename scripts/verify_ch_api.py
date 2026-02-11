#!/usr/bin/env python3
"""
Companies House API Integration - Quick Verification Script
Tests that the API integration is working correctly.
"""

import os
import sys
import json
import base64
from urllib import request, error

def check_env_file():
    """Check if .env file exists and has API key"""
    print("1. Checking .env file...")
    if not os.path.exists(".env"):
        print("   ❌ .env file not found")
        print("   → Create .env file with: CH_API_KEY=your_key_here")
        return False
    
    with open(".env", "r") as f:
        content = f.read()
        if "CH_API_KEY=" not in content:
            print("   ❌ CH_API_KEY not found in .env")
            return False
        
        # Extract key (basic parsing)
        for line in content.split("\n"):
            if line.startswith("CH_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key == "your_api_key_here" or not key:
                    print("   ❌ API key not configured (still placeholder)")
                    return False
                print(f"   ✅ API key found ({key[:8]}...)")
                return True
    
    print("   ❌ Could not parse API key")
    return False

def check_gitignore():
    """Check if .gitignore protects .env"""
    print("\n2. Checking .gitignore...")
    if not os.path.exists(".gitignore"):
        print("   ❌ .gitignore not found")
        return False
    
    with open(".gitignore", "r") as f:
        content = f.read()
        if ".env" in content:
            print("   ✅ .env is in .gitignore")
            return True
    
    print("   ❌ .env not found in .gitignore")
    return False

def check_api_files():
    """Check if new files exist"""
    print("\n3. Checking new files...")
    files = {
        "js/ch_api.js": "API client module",
        "COMPANIES_HOUSE_API.md": "Documentation"
    }
    
    all_ok = True
    for path, desc in files.items():
        if os.path.exists(path):
            print(f"   ✅ {desc}: {path}")
        else:
            print(f"   ❌ Missing: {path}")
            all_ok = False
    
    return all_ok

def test_api_connection():
    """Test direct connection to Companies House API"""
    print("\n4. Testing Companies House API connection...")
    
    # Get API key from environment
    if not os.path.exists(".env"):
        print("   ⚠️  Skipped (no .env file)")
        return False
    
    api_key = None
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("CH_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break
    
    if not api_key or api_key == "your_api_key_here":
        print("   ⚠️  Skipped (API key not configured)")
        return False
    
    # Test search endpoint
    try:
        url = "https://api.company-information.service.gov.uk/search/companies?q=tesco&items_per_page=1"
        auth = base64.b64encode(f"{api_key}:".encode()).decode()
        
        req = request.Request(url)
        req.add_header("Authorization", f"Basic {auth}")
        
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            if "items" in data and len(data["items"]) > 0:
                company = data["items"][0]
                print(f"   ✅ API working! Test result: {company.get('title', 'Unknown')}")
                return True
            else:
                print("   ⚠️  API returned no results")
                return False
    
    except error.HTTPError as e:
        if e.code == 401:
            print("   ❌ Authentication failed - check your API key")
        else:
            print(f"   ❌ HTTP Error {e.code}")
        return False
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False

def check_server_file():
    """Check dev_server.py exists"""
    print("\n5. Checking server file...")
    if os.path.exists("scripts/dev_server.py"):
        print("   ✅ scripts/dev_server.py exists")
        return True
    else:
        print("   ❌ scripts/dev_server.py not found")
        return False

def main():
    print("=" * 60)
    print("Companies House API Integration - Verification")
    print("=" * 60)
    
    checks = [
        check_env_file(),
        check_gitignore(),
        check_api_files(),
        test_api_connection(),
        check_server_file()
    ]
    
    print("\n" + "=" * 60)
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"✅ All checks passed ({passed}/{total})")
        print("\n🚀 Ready to test! Run:")
        print("   python scripts/dev_server.py")
        print("   Then open: http://localhost:8000")
    else:
        print(f"⚠️  Some checks failed ({passed}/{total} passed)")
        print("\nSee COMPANIES_HOUSE_API.md for setup instructions")
    
    print("=" * 60)
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
