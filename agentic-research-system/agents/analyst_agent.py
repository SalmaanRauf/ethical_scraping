import json
import asyncio
import re
from typing import List, Dict, Any
from config.kernel_setup import get_kernel
from semantic_kernel.functions import KernelFunction

class AnalystAgent:
    def __init__(self):
        self.kernel, self.exec_settings = get_kernel()
        self.functions = {}
        self._load_functions()
        
        # Configuration for intelligent text processing
        self.chunk_size = 3000  # Characters per chunk
        self.chunk_overlap = 500  # Overlap between chunks to avoid missing context
        self.max_chunks = 10  # Maximum chunks to process per document

    def _load_functions(self):
        """Load all Semantic Kernel functions."""
        try:
            # Load triage function
            self.functions['triage'] = self.kernel.add_function(
                prompt_template_file="sk_functions/Triage/skprompt.txt",
                function_name="triage",
                description="Categorize and filter data for relevance"
            )
            
            # Load financial specialist function
            self.functions['financial'] = self.kernel.add_function(
                prompt_template_file="sk_functions/FinancialSpecialist/skprompt.txt",
                function_name="financial_specialist",
                description="Detect financial events over $10M"
            )
            
            # Load procurement specialist function
            self.functions['procurement'] = self.kernel.add_function(
                prompt_template_file="sk_functions/ProcurementSpecialist/skprompt.txt",
                function_name="procurement_specialist",
                description="Analyze procurement notices"
            )
            
            # Load earnings call specialist function
            self.functions['earnings'] = self.kernel.add_function(
                prompt_template_file="sk_functions/EarningsCallSpecialist/skprompt.txt",
                function_name="earnings_specialist",
                description="Analyze earnings call transcripts"
            )
            
            # Load insight generator function
            self.functions['insight'] = self.kernel.add_function(
                prompt_template_file="sk_functions/InsightGenerator/skprompt.txt",
                function_name="insight_generator",
                description="Generate structured insights"
            )
            
            print("✅ All Semantic Kernel functions loaded successfully")
            
        except Exception as e:
            print(f"❌ Error loading functions: {e}")
            raise

    def _create_intelligent_chunks(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """
        Create intelligent chunks that preserve context and avoid cutting in the middle of important information.
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else []
        
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.chunk_overlap
        
        chunks = []
        start = 0
        
        while start < len(text) and len(chunks) < self.max_chunks:
            end = start + chunk_size
            
            # If this isn't the last chunk, try to find a good break point
            if end < len(text):
                # Look for sentence boundaries within the last 200 characters
                search_start = max(start + chunk_size - 200, start)
                search_end = min(start + chunk_size + 200, len(text))
                
                # Find the best sentence boundary
                best_break = end
                for i in range(search_start, search_end):
                    if text[i] in '.!?':
                        # Check if it's followed by a space and capital letter (likely sentence end)
                        if i + 1 < len(text) and text[i + 1] in ' \n\t':
                            if i + 2 < len(text) and text[i + 2].isupper():
                                best_break = i + 1
                                break
                
                end = best_break
            
            # Extract the chunk
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move to next chunk with overlap
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks

    def _extract_key_terms(self, text: str) -> List[str]:
        """
        Extract key terms that might indicate important financial information.
        """
        # Look for monetary amounts, company names, and key financial terms
        key_patterns = [
            r'\$\s*[0-9,.]+(?:\s*(?:million|billion|thousand|m|bn|k))?',  # Dollar amounts
            r'\b(?:Capital One|Fannie Mae|Freddie Mac|Navy Federal|PenFed|EagleBank|Capital Bank)\b',  # Company names
            r'\b(?:investment|acquisition|merger|partnership|funding|contract|deal|agreement)\b',  # Key terms
            r'\b(?:announces|launches|completes|signs|reports|discloses)\b'  # Action words
        ]
        
        key_terms = []
        for pattern in key_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            key_terms.extend(matches)
        
        return list(set(key_terms))  # Remove duplicates

    def _prioritize_chunks(self, chunks: List[str]) -> List[str]:
        """
        Prioritize chunks based on the presence of key financial terms.
        """
        if not chunks:
            return []
        
        chunk_scores = []
        for i, chunk in enumerate(chunks):
            score = 0
            key_terms = self._extract_key_terms(chunk)
            
            # Score based on key terms found
            score += len(key_terms) * 10
            
            # Bonus for chunks with dollar amounts
            if re.search(r'\$\s*[0-9,.]+', chunk):
                score += 50
            
            # Bonus for chunks with company names
            if re.search(r'\b(?:Capital One|Fannie Mae|Freddie Mac|Navy Federal|PenFed|EagleBank|Capital Bank)\b', chunk, re.IGNORECASE):
                score += 30
            
            # Bonus for chunks with action words
            if re.search(r'\b(?:announces|launches|completes|signs|reports|discloses)\b', chunk, re.IGNORECASE):
                score += 20
            
            chunk_scores.append((score, i, chunk))
        
        # Sort by score (highest first) and return chunks in priority order
        chunk_scores.sort(reverse=True)
        return [chunk for _, _, chunk in chunk_scores]

    async def _analyze_chunks_with_map_reduce(self, chunks: List[str], analysis_function: str, max_chunks: int = None) -> List[Dict[str, Any]]:
        """
        Analyze chunks using a map-reduce pattern to ensure comprehensive coverage.
        """
        if not chunks:
            return []
        
        max_chunks = max_chunks or self.max_chunks
        prioritized_chunks = self._prioritize_chunks(chunks)[:max_chunks]
        
        print(f"🔍 Analyzing {len(prioritized_chunks)} prioritized chunks (from {len(chunks)} total)")
        
        # Map: Analyze each chunk
        chunk_results = []
        for i, chunk in enumerate(prioritized_chunks):
            try:
                print(f"   📄 Analyzing chunk {i+1}/{len(prioritized_chunks)} ({len(chunk)} chars)")
                
                result = await self.kernel.invoke_function(
                    self.functions[analysis_function],
                    input_str=chunk
                )
                
                # Parse result
                try:
                    parsed_result = json.loads(str(result))
                    if parsed_result.get('event_found', False) or parsed_result.get('is_relevant', False):
                        chunk_results.append({
                            'chunk_index': i,
                            'chunk_text': chunk[:200] + "..." if len(chunk) > 200 else chunk,
                            'result': parsed_result,
                            'key_terms': self._extract_key_terms(chunk)
                        })
                        print(f"      ✅ Found relevant information in chunk {i+1}")
                    else:
                        print(f"      ⚪ No relevant information in chunk {i+1}")
                except json.JSONDecodeError:
                    print(f"      ⚠️  Could not parse result from chunk {i+1}")
                    continue
                    
            except Exception as e:
                print(f"      ❌ Error analyzing chunk {i+1}: {e}")
                continue
        
        # Reduce: Synthesize results from all chunks
        if chunk_results:
            print(f"   🔄 Synthesizing results from {len(chunk_results)} relevant chunks...")
            return self._synthesize_chunk_results(chunk_results, analysis_function)
        
        return []

    def _synthesize_chunk_results(self, chunk_results: List[Dict[str, Any]], analysis_type: str) -> List[Dict[str, Any]]:
        """
        Synthesize results from multiple chunks into a coherent analysis.
        """
        if not chunk_results:
            return []
        
        # For financial analysis, look for the highest value event
        if analysis_type == 'financial':
            max_value = 0
            best_result = None
            
            for chunk_result in chunk_results:
                result = chunk_result['result']
                value_usd = result.get('value_usd', 0)
                if value_usd and value_usd > max_value:
                    max_value = value_usd
                    best_result = result
            
            if best_result and max_value >= 10_000_000:
                return [{
                    'synthesized_result': best_result,
                    'source_chunks': len(chunk_results),
                    'max_value': max_value,
                    'analysis_type': 'financial'
                }]
        
        # For procurement analysis, combine all relevant notices
        elif analysis_type == 'procurement':
            relevant_results = []
            for chunk_result in chunk_results:
                result = chunk_result['result']
                if result.get('is_relevant', False) and result.get('value_usd', 0) >= 10_000_000:
                    relevant_results.append(result)
            
            if relevant_results:
                return [{
                    'synthesized_result': relevant_results[0],  # Take the first one as representative
                    'source_chunks': len(chunk_results),
                    'total_relevant': len(relevant_results),
                    'analysis_type': 'procurement'
                }]
        
        # For earnings analysis, combine all guidance found
        elif analysis_type == 'earnings':
            guidance_results = []
            for chunk_result in chunk_results:
                result = chunk_result['result']
                if result.get('guidance_found', False) and result.get('value_usd', 0) >= 10_000_000:
                    guidance_results.append(result)
            
            if guidance_results:
                return [{
                    'synthesized_result': guidance_results[0],  # Take the first one as representative
                    'source_chunks': len(chunk_results),
                    'total_guidance': len(guidance_results),
                    'analysis_type': 'earnings'
                }]
        
        return []

    async def triage_data(self, data_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Triage data to filter out irrelevant items using intelligent text processing."""
        relevant_items = []
        
        for item in data_items:
            try:
                # Prepare text for analysis
                text = ""
                if item.get('type') == 'news':
                    text = f"{item.get('title', '')} {item.get('summary', '')}"
                elif item.get('data_type') == 'filing':
                    text = item.get('text', '')
                elif item.get('type') == 'procurement':
                    text = f"{item.get('title', '')} {item.get('description', '')}"
                
                if not text.strip():
                    continue
                
                # For short texts, analyze directly
                if len(text) <= self.chunk_size:
                    result = await self.kernel.invoke_function(
                        self.functions['triage'],
                        input_str=text
                    )
                    
                    try:
                        triage_result = json.loads(str(result))
                        if triage_result.get('is_relevant', False):
                            item['triage_result'] = triage_result
                            relevant_items.append(item)
                    except json.JSONDecodeError:
                        continue
                else:
                    # For long texts, use intelligent chunking
                    chunks = self._create_intelligent_chunks(text)
                    prioritized_chunks = self._prioritize_chunks(chunks)[:3]  # Analyze top 3 chunks for triage
                    
                    # Analyze each prioritized chunk
                    for chunk in prioritized_chunks:
                        result = await self.kernel.invoke_function(
                            self.functions['triage'],
                            input_str=chunk
                        )
                        
                        try:
                            triage_result = json.loads(str(result))
                            if triage_result.get('is_relevant', False):
                                item['triage_result'] = triage_result
                                item['analyzed_chunks'] = len(chunks)
                                relevant_items.append(item)
                                print(f"✅ Found relevant content in {len(chunks)}-chunk document")
                                break
                        except json.JSONDecodeError:
                            continue
                    
            except Exception as e:
                print(f"Error during triage for item: {e}")
                continue
        
        print(f"Triage complete: {len(relevant_items)} relevant items found out of {len(data_items)}")
        return relevant_items

    async def analyze_financial_events(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze items for financial events using intelligent chunking."""
        financial_events = []
        
        for item in items:
            if item.get('triage_result', {}).get('category') in ['News Article', 'SEC Filing']:
                try:
                    text = ""
                    if item.get('type') == 'news':
                        text = f"{item.get('title', '')} {item.get('summary', '')}"
                    elif item.get('data_type') == 'filing':
                        text = item.get('text', '')
                    
                    if not text.strip():
                        continue
                    
                    # Use intelligent chunking for analysis
                    if len(text) <= self.chunk_size:
                        # Short text - analyze directly
                        result = await self.kernel.invoke_function(
                            self.functions['financial'],
                            input_str=text
                        )
                        
                        try:
                            financial_result = json.loads(str(result))
                            if financial_result.get('event_found', False):
                                value_usd = financial_result.get('value_usd', 0)
                                if value_usd and value_usd >= 10_000_000:
                                    item['financial_analysis'] = financial_result
                                    financial_events.append(item)
                        except json.JSONDecodeError:
                            continue
                    else:
                        # Long text - use map-reduce pattern
                        chunks = self._create_intelligent_chunks(text)
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'financial')
                        
                        if chunk_results:
                            # Use the synthesized result
                            synthesized = chunk_results[0]
                            if synthesized['synthesized_result'].get('event_found', False):
                                value_usd = synthesized['synthesized_result'].get('value_usd', 0)
                                if value_usd and value_usd >= 10_000_000:
                                    item['financial_analysis'] = synthesized['synthesized_result']
                                    item['analysis_metadata'] = {
                                        'chunks_analyzed': synthesized['source_chunks'],
                                        'analysis_method': 'map_reduce'
                                    }
                                    financial_events.append(item)
                                    print(f"✅ Found financial event (${value_usd:,}) using {synthesized['source_chunks']} chunks")
                        
                except Exception as e:
                    print(f"Error during financial analysis: {e}")
                    continue
        
        print(f"Financial analysis complete: {len(financial_events)} events >= $10M found")
        return financial_events

    async def analyze_procurement(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze procurement notices using intelligent chunking."""
        procurement_events = []
        
        for item in items:
            if item.get('type') == 'procurement':
                try:
                    text = f"{item.get('title', '')} {item.get('description', '')}"
                    
                    if not text.strip():
                        continue
                    
                    # Use intelligent chunking for analysis
                    if len(text) <= self.chunk_size:
                        # Short text - analyze directly
                        result = await self.kernel.invoke_function(
                            self.functions['procurement'],
                            input_str=text
                        )
                        
                        try:
                            procurement_result = json.loads(str(result))
                            if procurement_result.get('is_relevant', False):
                                value_usd = procurement_result.get('value_usd', 0)
                                if value_usd and value_usd >= 10_000_000:
                                    item['procurement_analysis'] = procurement_result
                                    procurement_events.append(item)
                        except json.JSONDecodeError:
                            continue
                    else:
                        # Long text - use map-reduce pattern
                        chunks = self._create_intelligent_chunks(text)
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'procurement')
                        
                        if chunk_results:
                            # Use the synthesized result
                            synthesized = chunk_results[0]
                            if synthesized['synthesized_result'].get('is_relevant', False):
                                value_usd = synthesized['synthesized_result'].get('value_usd', 0)
                                if value_usd and value_usd >= 10_000_000:
                                    item['procurement_analysis'] = synthesized['synthesized_result']
                                    item['analysis_metadata'] = {
                                        'chunks_analyzed': synthesized['source_chunks'],
                                        'analysis_method': 'map_reduce'
                                    }
                                    procurement_events.append(item)
                                    print(f"✅ Found procurement event (${value_usd:,}) using {synthesized['source_chunks']} chunks")
                        
                except Exception as e:
                    print(f"Error during procurement analysis: {e}")
                    continue
        
        print(f"Procurement analysis complete: {len(procurement_events)} relevant notices >= $10M found")
        return procurement_events

    async def analyze_earnings_calls(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze earnings call transcripts using intelligent chunking."""
        earnings_events = []
        
        for item in items:
            if (item.get('data_type') == 'filing' and 
                item.get('type') in ['10-Q', '10-K']):
                try:
                    text = item.get('text', '')
                    
                    if not text.strip():
                        continue
                    
                    # Use intelligent chunking for analysis
                    if len(text) <= self.chunk_size:
                        # Short text - analyze directly
                        result = await self.kernel.invoke_function(
                            self.functions['earnings'],
                            input_str=text
                        )
                        
                        try:
                            earnings_result = json.loads(str(result))
                            if earnings_result.get('guidance_found', False):
                                value_usd = earnings_result.get('value_usd', 0)
                                if value_usd and value_usd >= 10_000_000:
                                    item['earnings_analysis'] = earnings_result
                                    earnings_events.append(item)
                        except json.JSONDecodeError:
                            continue
                    else:
                        # Long text - use map-reduce pattern
                        chunks = self._create_intelligent_chunks(text)
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'earnings')
                        
                        if chunk_results:
                            # Use the synthesized result
                            synthesized = chunk_results[0]
                            if synthesized['synthesized_result'].get('guidance_found', False):
                                value_usd = synthesized['synthesized_result'].get('value_usd', 0)
                                if value_usd and value_usd >= 10_000_000:
                                    item['earnings_analysis'] = synthesized['synthesized_result']
                                    item['analysis_metadata'] = {
                                        'chunks_analyzed': synthesized['source_chunks'],
                                        'analysis_method': 'map_reduce'
                                    }
                                    earnings_events.append(item)
                                    print(f"✅ Found earnings guidance (${value_usd:,}) using {synthesized['source_chunks']} chunks")
                        
                except Exception as e:
                    print(f"Error during earnings call analysis: {e}")
                    continue
        
        print(f"Earnings call analysis complete: {len(earnings_events)} guidance items >= $10M found")
        return earnings_events

    async def generate_insights(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate insights for all events."""
        insights = []
        
        for event in events:
            try:
                # Prepare data for insight generation
                insight_data = {
                    'company': event.get('company', ''),
                    'title': event.get('title', ''),
                    'source': event.get('source', ''),
                    'type': event.get('type', '')
                }
                
                # Add analysis results
                if 'financial_analysis' in event:
                    insight_data.update(event['financial_analysis'])
                elif 'procurement_analysis' in event:
                    insight_data.update(event['procurement_analysis'])
                elif 'earnings_analysis' in event:
                    insight_data.update(event['earnings_analysis'])
                
                # Generate insight
                result = await self.kernel.invoke_function(
                    self.functions['insight'],
                    input_str=json.dumps(insight_data)
                )
                
                # Parse result
                try:
                    insight_result = json.loads(str(result))
                    event['insights'] = insight_result
                    insights.append(event)
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse insight for event: {event.get('title', 'Unknown')}")
                    continue
                    
            except Exception as e:
                print(f"Error generating insight: {e}")
                continue
        
        print(f"Insight generation complete: {len(insights)} insights generated")
        return insights

    async def analyze_all_data(self, data_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Main method to analyze all data through the complete pipeline."""
        print(f"Starting analysis of {len(data_items)} data items...")
        
        # Step 1: Triage
        relevant_items = await self.triage_data(data_items)
        
        # Step 2: Specialized analysis
        financial_events = await self.analyze_financial_events(relevant_items)
        procurement_events = await self.analyze_procurement(relevant_items)
        earnings_events = await self.analyze_earnings_calls(relevant_items)
        
        # Step 3: Combine all events
        all_events = financial_events + procurement_events + earnings_events
        
        # Step 4: Generate insights
        final_insights = await self.generate_insights(all_events)
        
        print(f"Analysis complete: {len(final_insights)} high-impact events identified")
        return final_insights 