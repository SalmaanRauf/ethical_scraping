#!/usr/bin/env python3
"""
Comprehensive test runner for the single-company briefing system.
"""

import sys
import subprocess
import time
from pathlib import Path
from typing import List, Dict

class TestRunner:
    """Manages test execution and reporting."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.test_results = {}
        self.start_time = None
    
    def run_unit_tests(self) -> bool:
        """Run unit tests."""
        print("🧪 Running unit tests...")
        
        test_files = [
            "tests/test_company_resolver.py",
            "tests/test_single_company_workflow.py"
        ]
        
        success = True
        for test_file in test_files:
            if Path(test_file).exists():
                result = subprocess.run([
                    sys.executable, "-m", "pytest", test_file, "-v"
                ], capture_output=True, text=True)
                
                self.test_results[f"unit_{test_file}"] = {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr
                }
                
                if result.returncode != 0:
                    success = False
                    print(f"❌ Unit test failed: {test_file}")
                else:
                    print(f"✅ Unit test passed: {test_file}")
        
        return success
    
    def run_integration_tests(self) -> bool:
        """Run integration tests."""
        print("🔗 Running integration tests...")
        
        test_files = [
            "tests/test_integration.py",
            "tests/test_chainlit_integration.py"
        ]
        
        success = True
        for test_file in test_files:
            if Path(test_file).exists():
                result = subprocess.run([
                    sys.executable, "-m", "pytest", test_file, "-v"
                ], capture_output=True, text=True)
                
                self.test_results[f"integration_{test_file}"] = {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr
                }
                
                if result.returncode != 0:
                    success = False
                    print(f"❌ Integration test failed: {test_file}")
                else:
                    print(f"✅ Integration test passed: {test_file}")
        
        return success
    
    def run_system_tests(self) -> bool:
        """Run system-level tests."""
        print("🖥️  Running system tests...")
        
        # Test company resolver
        try:
            from agents.company_resolver import CompanyResolver
            resolver = CompanyResolver()
            slug, display = resolver.resolve_company("Capital One")
            
            if slug == "Capital_One" and display == "Capital One Financial Corporation":
                print("✅ Company resolver test passed")
                self.test_results['system_company_resolver'] = {'success': True}
            else:
                print("❌ Company resolver test failed")
                self.test_results['system_company_resolver'] = {'success': False}
                return False
                
        except Exception as e:
            print(f"❌ Company resolver test failed: {e}")
            self.test_results['system_company_resolver'] = {'success': False, 'error': str(e)}
            return False
        
        # Test profile loader
        try:
            from services.profile_loader import ProfileLoader
            loader = ProfileLoader()
            profiles = loader.get_available_profiles()
            
            if isinstance(profiles, list):
                print("✅ Profile loader test passed")
                self.test_results['system_profile_loader'] = {'success': True}
            else:
                print("❌ Profile loader test failed")
                self.test_results['system_profile_loader'] = {'success': False}
                return False
                
        except Exception as e:
            print(f"❌ Profile loader test failed: {e}")
            self.test_results['system_profile_loader'] = {'success': False, 'error': str(e)}
            return False
        
        return True
    
    def run_performance_tests(self) -> bool:
        """Run performance tests."""
        print("⚡ Running performance tests...")
        
        # Test import performance
        import_start = time.time()
        try:
            from agents.single_company_workflow import SingleCompanyWorkflow
            from agents.company_resolver import CompanyResolver
            from services.profile_loader import ProfileLoader
            import_time = time.time() - import_start
            
            if import_time < 5.0:  # Should import in under 5 seconds
                print(f"✅ Import performance test passed ({import_time:.2f}s)")
                self.test_results['performance_import'] = {'success': True, 'time': import_time}
            else:
                print(f"❌ Import performance test failed ({import_time:.2f}s)")
                self.test_results['performance_import'] = {'success': False, 'time': import_time}
                return False
                
        except Exception as e:
            print(f"❌ Import performance test failed: {e}")
            self.test_results['performance_import'] = {'success': False, 'error': str(e)}
            return False
        
        return True
    
    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n" + "="*60)
        print("📊 TEST REPORT")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if self.start_time:
            duration = time.time() - self.start_time
            print(f"Total Duration: {duration:.2f}s")
        
        print("\nDetailed Results:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            print(f"  {test_name}: {status}")
            
            if 'error' in result:
                print(f"    Error: {result['error']}")
        
        if failed_tests == 0:
            print("\n🎉 All tests passed! System is ready for deployment.")
            return True
        else:
            print(f"\n⚠️  {failed_tests} test(s) failed. Please review before deployment.")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all test suites."""
        self.start_time = time.time()
        
        print("🚀 Starting comprehensive test suite...")
        print("="*60)
        
        # Run all test types
        unit_success = self.run_unit_tests()
        integration_success = self.run_integration_tests()
        system_success = self.run_system_tests()
        performance_success = self.run_performance_tests()
        
        # Generate report
        overall_success = self.generate_report()
        
        return overall_success and unit_success and integration_success and system_success and performance_success

def main():
    """Main test runner function."""
    runner = TestRunner()
    
    try:
        success = runner.run_all_tests()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n🛑 Test execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 