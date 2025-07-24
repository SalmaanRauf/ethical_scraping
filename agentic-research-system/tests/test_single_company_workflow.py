"""
Integration tests for single company workflow.
"""

import unittest
import asyncio
from agents.single_company_workflow import SingleCompanyWorkflow

class TestSingleCompanyWorkflow(unittest.TestCase):
    
    def setUp(self):
        self.workflow = SingleCompanyWorkflow()
    
    def test_workflow_execution(self):
        """Test complete workflow execution."""
        async def test_execution():
            result = await self.workflow.execute("Capital_One")
            self.assertIn('status', result)
            self.assertIn('company_slug', result)
        
        asyncio.run(test_execution())
    
    def test_error_handling(self):
        """Test error handling with invalid company."""
        async def test_error():
            result = await self.workflow.execute("Invalid_Company")
            self.assertEqual(result['status'], 'failed')
        
        asyncio.run(test_error())

if __name__ == '__main__':
    unittest.main()
