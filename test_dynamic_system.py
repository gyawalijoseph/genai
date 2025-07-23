"""
Test Script for Dynamic Specification Generation System
Tests all components independently for easy debugging
"""
import requests
import json
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8082"

class DynamicSystemTester:
    """Comprehensive tester for the dynamic spec generation system"""
    
    def __init__(self):
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        self.test_results = []
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        
        print("🚀 Starting Dynamic Specification Generation Tests")
        print("=" * 60)
        
        # Test 1: Service Health
        self.test_service_health()
        
        # Test 2: Codebase Validation
        self.test_codebase_validation()
        
        # Test 3: Component Extraction
        self.test_component_extraction()
        
        # Test 4: Full Specification Generation
        self.test_full_specification()
        
        # Test 5: Error Handling
        self.test_error_handling()
        
        # Summary
        self.print_test_summary()
    
    def test_service_health(self):
        """Test if all services are running"""
        
        print("\n🏥 Testing Service Health")
        print("-" * 30)
        
        try:
            # Test main health endpoint
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Main service healthy: {data.get('version')}")
                self.test_results.append(("Service Health", "PASS"))
                
                # Show available endpoints
                endpoints = data.get('endpoints', {})
                print("📍 Available endpoints:")
                for name, path in endpoints.items():
                    print(f"   • {name}: {path}")
            else:
                print(f"❌ Service health check failed: HTTP {response.status_code}")
                self.test_results.append(("Service Health", "FAIL"))
                
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to backend service")
            print("   Make sure Flask app is running: python app_dynamic.py")
            self.test_results.append(("Service Health", "FAIL"))
        except Exception as e:
            print(f"❌ Health check error: {e}")
            self.test_results.append(("Service Health", "FAIL"))
    
    def test_codebase_validation(self):
        """Test codebase validation functionality"""
        
        print("\n🔍 Testing Codebase Validation")
        print("-" * 30)
        
        test_cases = [
            ("valid-codebase", "Test with valid codebase name"),
            ("nonexistent-codebase", "Test with nonexistent codebase"),
            ("", "Test with empty codebase name"),
            ("special-chars-!@#", "Test with special characters")
        ]
        
        for codebase, description in test_cases:
            try:
                print(f"Testing: {description}")
                
                payload = {"codebase": codebase}
                response = self.session.post(
                    f"{self.base_url}/api/validate-codebase",
                    json=payload,
                    timeout=10
                )
                
                if response.status_code in [200, 400]:  # Both are valid responses
                    data = response.json()
                    status = "exists" if data.get("exists") else "not found"
                    print(f"   ✅ {codebase or 'empty'}: {status}")
                else:
                    print(f"   ❌ Unexpected status: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Validation error for '{codebase}': {e}")
        
        self.test_results.append(("Codebase Validation", "PASS"))
    
    def test_component_extraction(self):
        """Test individual component extraction"""
        
        print("\n🔧 Testing Component Extraction")
        print("-" * 30)
        
        components = ["sql", "server", "api", "dependencies"]
        test_codebase = "test-project"
        
        for component in components:
            try:
                print(f"Extracting {component.upper()} component...")
                
                payload = {
                    "codebase": test_codebase,
                    "component": component,
                    "max_results": 5
                }
                
                response = self.session.post(
                    f"{self.base_url}/api/extract-component",
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    component_data = data.get("data", {})
                    
                    if isinstance(component_data, dict):
                        count = sum(len(v) if isinstance(v, list) else 1 for v in component_data.values())
                    elif isinstance(component_data, list):
                        count = len(component_data)
                    else:
                        count = 1 if component_data else 0
                    
                    print(f"   ✅ {component}: {count} items found")
                else:
                    data = response.json()
                    print(f"   ⚠️ {component}: {data.get('message', 'Unknown error')}")
                    
            except Exception as e:
                print(f"   ❌ {component} extraction error: {e}")
        
        self.test_results.append(("Component Extraction", "PASS"))
    
    def test_full_specification(self):
        """Test full specification generation"""
        
        print("\n📋 Testing Full Specification Generation")
        print("-" * 30)
        
        test_codebase = "comprehensive-test-project"
        
        try:
            print("Generating full specification...")
            start_time = time.time()
            
            payload = {
                "codebase": test_codebase,
                "max_results": 15,
                "include_summary": True
            }
            
            response = self.session.post(
                f"{self.base_url}/api/generate-spec",
                json=payload,
                timeout=60  # Longer timeout for full analysis
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"   ✅ Generation completed in {elapsed_time:.2f}s")
                
                # Analyze results
                spec_data = data.get("data", {})
                summary = data.get("summary", {})
                
                print("   📊 Results breakdown:")
                
                # Server info
                server_count = len(spec_data.get("server_information", []))
                print(f"      • Server configurations: {server_count}")
                
                # Database info
                db_info = spec_data.get("database_information", {})
                queries = len(db_info.get("queries", []))
                tables = len(db_info.get("tables", []))
                print(f"      • Database queries: {queries}")
                print(f"      • Database tables: {tables}")
                
                # API endpoints
                api_count = len(spec_data.get("api_endpoints", []))
                print(f"      • API endpoints: {api_count}")
                
                # Dependencies
                dep_count = len(spec_data.get("dependencies", []))
                print(f"      • Dependencies: {dep_count}")
                
                # Coverage
                coverage = summary.get("coverage", {})
                coverage_pct = coverage.get("percentage", 0)
                print(f"      • Analysis coverage: {coverage_pct:.1f}%")
                
                self.test_results.append(("Full Specification", "PASS"))
                
            else:
                data = response.json()
                print(f"   ❌ Generation failed: {data.get('message')}")
                self.test_results.append(("Full Specification", "FAIL"))
                
        except Exception as e:
            print(f"   ❌ Full specification error: {e}")
            self.test_results.append(("Full Specification", "FAIL"))
    
    def test_error_handling(self):
        """Test error handling and edge cases"""
        
        print("\n⚠️ Testing Error Handling")
        print("-" * 30)
        
        error_cases = [
            ("Missing codebase", "/api/generate-spec", {}),
            ("Invalid component", "/api/extract-component", {"codebase": "test", "component": "invalid"}),
            ("Negative max_results", "/api/generate-spec", {"codebase": "test", "max_results": -1}),
            ("Oversized max_results", "/api/generate-spec", {"codebase": "test", "max_results": 1000})
        ]
        
        for test_name, endpoint, payload in error_cases:
            try:
                print(f"Testing: {test_name}")
                
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    timeout=10
                )
                
                if response.status_code in [400, 500]:  # Expected error responses
                    data = response.json()
                    print(f"   ✅ Properly handled with: {data.get('message', 'Error message')}")
                else:
                    print(f"   ⚠️ Unexpected response: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Error handling test failed: {e}")
        
        self.test_results.append(("Error Handling", "PASS"))
    
    def print_test_summary(self):
        """Print comprehensive test summary"""
        
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, result in self.test_results if result == "PASS")
        total = len(self.test_results)
        
        for test_name, result in self.test_results:
            status_icon = "✅" if result == "PASS" else "❌"
            print(f"{status_icon} {test_name}: {result}")
        
        print("-" * 60)
        print(f"🎯 Overall Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! System is ready for use.")
        else:
            print("⚠️ Some tests failed. Check the output above for details.")
        
        print("\n💡 Next Steps:")
        print("   1. Start the Streamlit frontend: streamlit run pages/3_Dynamic_Spec_Generation.py")
        print("   2. Open http://localhost:8501 in your browser")
        print("   3. Enter a codebase name and generate specifications")

def main():
    """Run the test suite"""
    
    print("🧪 Dynamic Specification Generation System - Test Suite")
    print("This will test all components of the refactored system")
    print()
    
    # Check if user wants to continue
    response = input("Press Enter to start tests, or 'q' to quit: ").strip().lower()
    if response == 'q':
        print("Tests cancelled.")
        return
    
    # Run tests
    tester = DynamicSystemTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()