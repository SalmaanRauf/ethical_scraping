#!/usr/bin/env python3
"""
Full Workflow Simulation - No API Keys Required
Demonstrates the complete end-to-end process from user input to final report.
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Mock the API keys to avoid errors (Azure AI Foundry)
os.environ['SEC_API_KEY'] = 'mock_key'
os.environ['GNEWS_API_KEY'] = 'mock_key'
os.environ['SAM_API_KEY'] = 'mock_key'
os.environ['OPENAI_API_KEY'] = 'mock_key'
os.environ['BASE_URL'] = 'mock_endpoint'
os.environ['PROJECT_ID'] = 'mock_project'
os.environ['API_VERSION'] = '2024-02-15-preview'
os.environ['MODEL'] = 'gpt-4o'
os.environ['PROJECT_ENDPOINT'] = 'mock_project_endpoint'
os.environ['MODEL_DEPLOYMENT_NAME'] = 'mock_deployment'
os.environ['AZURE_BING_CONNECTION_ID'] = 'mock_bing_connection'

def print_step(step_num, title):
    """Print a formatted step header."""
    print(f'\n📋 STEP {step_num}: {title}')
    print('-' * 50)

async def simulate_full_workflow():
    """Simulate the complete workflow from user input to final report."""
    
    print('🚀 Starting Full Workflow Simulation...')
    print('=' * 60)
    print(f'⏰ Simulation started at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    
    # Step 1: Company Resolution
    print_step(1, "Company Resolution")
    try:
        from agents.company_resolver import CompanyResolver
        resolver = CompanyResolver()
        canonical_name, display_name = resolver.resolve_company('Capital One')
        print(f'✅ Resolved: "Capital One" → {canonical_name} ({display_name})')
        
        # Test additional company names
        test_companies = ['Fannie Mae', 'Navy Federal', 'Unknown Company']
        for company in test_companies:
            result = resolver.resolve_company(company)
            status = "✅" if result[0] else "❌"
            print(f'{status} "{company}" → {result}')
            
    except Exception as e:
        print(f'❌ Company resolution failed: {e}')
        return

    # Step 2: Profile Loading
    print_step(2, "Profile Loading")
    try:
        from services.profile_loader import ProfileLoader
        profile_loader = ProfileLoader()
        
        # Load single profile
        profile = profile_loader.load_company_profile(canonical_name)
        if profile:
            print(f'✅ Loaded profile for {canonical_name}')
            print(f'   - Company: {profile.get("company_name", "N/A")}')
            print(f'   - Industry: {profile.get("industry", "N/A")}')
            print(f'   - Revenue: {profile.get("revenue", "N/A")}')
        else:
            print(f'⚠️  Profile not found for {canonical_name}')
        
        # Load all profiles
        all_profiles = profile_loader.load_profiles()
        print(f'📊 Total profiles loaded: {len(all_profiles)}')
        
    except Exception as e:
        print(f'❌ Profile loading failed: {e}')
        return

    # Step 3: Data Consolidation
    print_step(3, "Data Consolidation")
    try:
        from agents.data_consolidator import DataConsolidator
        consolidator = DataConsolidator(profile_loader)

        # Mock raw data from different sources - using "Company Name" to match the profile
        mock_raw_data = [
            {
                'title': 'Company Name Reports Strong Q4 Earnings',
                'description': 'Company Name reported quarterly earnings of $2.5 billion, exceeding analyst expectations by 15%.',
                'source': 'SEC Filing',
                'url': 'https://sec.gov/filing/example',
                'published_date': '2024-01-15',
                'content': 'Company Name today announced net income of $2.5 billion for the fourth quarter of 2023, representing a 12% increase over the prior year quarter. The strong performance was driven by growth in credit card lending and improved credit quality.'
            },
            {
                'title': 'Company Name Announces $500M Technology Investment',
                'description': 'Company Name is investing $500 million in digital transformation initiatives including AI and cloud infrastructure.',
                'source': 'News Article',
                'url': 'https://example.com/news',
                'published_date': '2024-01-10',
                'content': 'Company Name announced today a major investment in technology infrastructure. The $500 million initiative will focus on artificial intelligence, cloud computing, and cybersecurity enhancements.'
            },
            {
                'title': 'SAM.gov: IT Security Services RFP for Company Name',
                'description': 'Company Name seeking IT security consulting services, estimated value $25M',
                'source': 'SAM.gov',
                'url': 'https://sam.gov/opportunity/example',
                'published_date': '2024-01-12',
                'content': 'Company Name is seeking qualified vendors for comprehensive IT security services including penetration testing, security assessments, and compliance consulting. Estimated contract value: $25 million.'
            },
            {
                'title': 'Company Name Expands Digital Banking Platform',
                'description': 'New mobile app features and enhanced online banking capabilities launched by Company Name.',
                'source': 'News Article',
                'url': 'https://example.com/digital',
                'published_date': '2024-01-08',
                'content': 'Company Name has launched enhanced digital banking features including improved mobile app functionality, real-time fraud detection, and personalized financial insights powered by machine learning.'
            }
        ]

        print(f'📥 Processing {len(mock_raw_data)} raw data items...')
        consolidation_result = consolidator.process_raw_data(mock_raw_data)
        
        print(f'✅ Processed {len(mock_raw_data)} raw items')
        print(f'✅ Found {len(consolidation_result["consolidated_items"])} relevant items')
        print(f'✅ Generated analysis document ({len(consolidation_result["analysis_document"])} chars)')
        
        # Show sample of consolidated items
        for i, item in enumerate(consolidation_result["consolidated_items"][:2]):
            print(f'   Item {i+1}: {item["title"][:60]}... (Score: {item["relevance_score"]:.2f})')
            
    except Exception as e:
        print(f'❌ Data consolidation failed: {e}')
        return

    # Step 4: AI Analysis
    print_step(4, "AI Analysis")
    try:
        from agents.analyst_agent import AnalystAgent

        # Create a mock analyst agent that doesn't require real API calls
        class MockAnalystAgent(AnalystAgent):
            def __init__(self, chunk_size: int = 3000, chunk_overlap: int = 500, max_chunks: int = 10):
                # Skip kernel initialization for mock
                self.functions = {}
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap
                self.max_chunks = max_chunks
                self.company_profiles = {}
                print("✅ Mock analyst agent initialized (no kernel required)")
            
            async def _ensure_kernel_initialized(self):
                # Skip kernel initialization for mock
                pass
                
            async def _invoke_function_safely(self, function_name: str, input_text: str):
                # Return mock analysis results based on function type
                if function_name == 'triage':
                    return '{"is_relevant": true, "category": "News Article"}'
                elif function_name == 'financial':
                    return '{"event_found": true, "value_usd": 2500000000, "event_type": "earnings", "description": "Strong quarterly earnings report"}'
                elif function_name == 'procurement':
                    return '{"is_relevant": true, "value_usd": 25000000, "opportunity_type": "IT Security", "description": "IT security consulting services RFP"}'
                elif function_name == 'earnings':
                    return '{"guidance_found": true, "value_usd": 2500000000, "guidance_type": "revenue", "description": "Positive revenue guidance"}'
                elif function_name == 'insight':
                    return '{"what_happened": "Strong earnings and technology investment", "why_it_matters": "Shows financial strength and digital transformation focus", "consulting_angle": "Digital transformation and IT security opportunities", "priority": "high", "timeline": "immediate", "service_categories": ["Digital Transformation", "IT Security", "Financial Advisory"]}'
                elif function_name == 'company_takeaway':
                    return '{"summary": "Capital One is in growth mode with strong financials. Focus on digital transformation and IT security opportunities. Leverage existing relationships for upselling."}'
                return None

        # Set up mock profiles
        mock_profiles = {canonical_name: profile} if profile else {}
        analyst = MockAnalystAgent()
        analyst.set_profiles(mock_profiles)

        # Run analysis
        consolidated_items = consolidation_result['consolidated_items']
        analysis_document = consolidation_result['analysis_document']

        print('🔍 Running AI analysis...')
        analyzed_events = await analyst.analyze_consolidated_data(consolidated_items, analysis_document)
        print(f'✅ Analysis complete: {len(analyzed_events)} high-impact events identified')
        
        # Show sample analysis results
        for i, event in enumerate(analyzed_events[:2]):
            insights = event.get('insights', {})
            print(f'   Event {i+1}: {event["title"][:50]}...')
            print(f'      - What: {insights.get("what_happened", "N/A")[:60]}...')
            print(f'      - Angle: {insights.get("consulting_angle", "N/A")[:60]}...')
            
    except Exception as e:
        print(f'❌ AI analysis failed: {e}')
        return

    # Step 5: Report Generation
    print_step(5, "Report Generation")
    try:
        # Create mock workflow for report generation
        class MockWorkflow:
            def _generate_briefing(self, display_name, events, profile):
                briefing = f"# Intelligence Briefing: {display_name}\n\n"
                
                # Company Profile Section
                briefing += "## Company Profile\n"
                if profile:
                    briefing += f"**Description:** {profile.get('description', 'N/A')}\n"
                    briefing += f"**Industry:** {profile.get('industry', 'N/A')}\n"
                    briefing += f"**Revenue:** {profile.get('revenue', 'N/A')}\n"
                
                # Proprietary Insights Section
                briefing += "\n## Proprietary Company Insights\n"
                if profile and profile.get('people'):
                    if profile['people'].get('keyBuyers'):
                        briefing += "### Key Buyers\n"
                        for buyer in profile['people']['keyBuyers'][:2]:  # Show first 2
                            briefing += f"- **{buyer.get('name', 'N/A')}**: {buyer.get('title', 'N/A')} (Wins: {buyer.get('numberOfWins', 0)})\n"
                    
                    if profile['people'].get('alumni'):
                        briefing += "### Alumni Contacts\n"
                        for alumni in profile['people']['alumni'][:2]:  # Show first 2
                            briefing += f"- **{alumni.get('name', 'N/A')}**: {alumni.get('title', 'N/A')}\n"
                
                # Key Events Section
                briefing += "\n## Key Recent Events\n"
                for event in events:
                    insights = event.get('insights', {})
                    briefing += f"\n### {event.get('title', 'Untitled Event')}\n"
                    briefing += f"- **What Happened:** {insights.get('what_happened', 'N/A')}\n"
                    briefing += f"- **Why It Matters:** {insights.get('why_it_matters', 'N/A')}\n"
                    briefing += f"- **Consulting Angle:** {insights.get('consulting_angle', 'N/A')}\n"
                    briefing += f"- **Priority:** {insights.get('priority', 'N/A').title()}\n"
                    briefing += f"- **Timeline:** {insights.get('timeline', 'N/A').title()}\n"
                    if event.get('url'):
                        briefing += f"- **Source:** [Link]({event.get('url')})\n"
                
                # Company Takeaway Section
                if events and events[0].get('company_takeaway'):
                    briefing += "\n## Company Takeaway\n"
                    takeaway = events[0].get('company_takeaway', {})
                    if isinstance(takeaway, str):
                        briefing += f"{takeaway}\n"
                    else:
                        briefing += f"{takeaway.get('summary', 'N/A')}\n"
                
                return briefing

        workflow = MockWorkflow()
        report = workflow._generate_briefing(display_name, analyzed_events, profile)
        print('✅ Report generated successfully')
        print(f'📄 Report length: {len(report)} characters')
        
    except Exception as e:
        print(f'❌ Report generation failed: {e}')
        return

    # Step 6: Final Output
    print_step(6, "Final Output")
    print('🎯 WORKFLOW COMPLETE!')
    print('=' * 60)
    print('📊 SUMMARY:')
    print(f'   - Company: {display_name}')
    print(f'   - Raw data items: {len(mock_raw_data)}')
    print(f'   - Relevant items: {len(consolidation_result["consolidated_items"])}')
    print(f'   - High-impact events: {len(analyzed_events)}')
    print(f'   - Report generated: ✅')
    print(f'   - Total execution time: {datetime.now().strftime("%H:%M:%S")}')

    print('\n📋 SAMPLE REPORT:')
    print('-' * 50)
    print(report[:800] + '...' if len(report) > 800 else report)

    print('\n🎉 Full workflow simulation completed successfully!')
    print('💡 This demonstrates the complete end-to-end process without requiring any API keys.')
    print('🔧 To run with real data, add your API keys to the .env file and use the actual workflow.')

if __name__ == "__main__":
    asyncio.run(simulate_full_workflow()) 