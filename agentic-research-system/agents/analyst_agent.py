import json
import asyncio
import re
import os
from typing import List, Dict, Any, Optional
from config.kernel_setup import get_kernel, get_kernel_async
from semantic_kernel.functions import KernelFunction
from dataclasses import dataclass

class AnalystAgent:
    def __init__(self, chunk_size: int = 3000, chunk_overlap: int = 500, max_chunks: int = 10):
        # Try to get kernel synchronously first
        try:
            self.kernel, self.exec_settings = get_kernel()
        except RuntimeError:
            # If we're in an async context, we'll need to initialize later
            self.kernel = None
            self.exec_settings = None
        
        self.functions = {}
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunks = max_chunks
        self._load_functions()
        
    async def _ensure_kernel_initialized(self):
        """Ensure kernel is initialized, especially in async contexts."""
        if self.kernel is None or self.exec_settings is None:
            self.kernel, self.exec_settings = await get_kernel_async()
            # Reload functions with the new kernel
            self._load_functions()
        
    def _load_functions(self):
        """Load all Semantic Kernel functions using the correct 1.34.0 API."""
        # Get the correct path to sk_functions directory
        sk_dir = os.path.join(os.path.dirname(__file__), "..", "sk_functions")
        
        prompt_files = {
            "triage": "Triage_CategoryRouting_prompt.txt",
            "financial": "FinancialEvent_Detection_prompt.txt", 
            "procurement": "OpportunityIdent_skprompt.txt",
            "earnings": "EarningsCall_GuidanceAnalysis_prompt.txt",
            "insight": "StrategicInsight_Generation_prompt.txt"
        }

        for name, fname in prompt_files.items():
            path = os.path.normpath(os.path.join(sk_dir, fname))
            try:
                with open(path, "r", encoding="utf-8") as f:
                    template = f.read()
                
                # Create function with proper parameter names
                func = KernelFunction.from_prompt(
                    prompt=template,
                    function_name=name,
                    plugin_name="analyst_plugin",
                    parameter_names=["input"],
                    description=f"{name} analysis function"
                )
                self.functions[name] = func
                
                if self.kernel:
                    try:
                        self.kernel.add_function(func)
                    except Exception as ex:
                        print(f"⚠️  Failed to add SK function '{name}': {ex}")
                        
            except FileNotFoundError:
                print(f"❌ Prompt file not found: {path}")
            except Exception as e:
                print(f"❌ Error loading prompt '{name}' from {path}: {e}")
                # Continue loading other functions even if one fails
        
        print(f"✅ Loaded {len(self.functions)} Semantic Kernel functions successfully")

    def _create_intelligent_chunks(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """
        Create intelligent chunks that preserve context and avoid cutting in the middle of important information.
        """
        if not text:
            return []
        
        # Memory safety checks
        if len(text) > 10_000_000:  # 10MB limit
            print(f"⚠️  Text too large ({len(text)} chars), truncating to 10MB")
            text = text[:10_000_000]
        
        if len(text) <= chunk_size:
            return [text]
        
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.chunk_overlap
        
        # Monitor memory usage (optional - requires psutil)
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss
        except ImportError:
            process = None
            initial_memory = 0
        
        chunks = []
        start = 0
        
        while start < len(text) and len(chunks) < self.max_chunks:
            # Check memory usage periodically
            if process and len(chunks) % 10 == 0:
                current_memory = process.memory_info().rss
                if current_memory - initial_memory > 500_000_000:  # 500MB increase
                    print("⚠️  Memory usage too high, stopping chunk creation")
                    break
            
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
        
        # PARALLEL PROCESSING
        tasks = []
        for i, chunk in enumerate(prioritized_chunks):
            tasks.append(self._analyze_single_chunk(i, chunk, analysis_function))
        
        chunk_results = []
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ Task {i} failed: {result}")
                elif result:
                    chunk_results.append(result)
        except Exception as e:
            print(f"❌ Gather operation failed: {e}")
        
        return self._synthesize_chunk_results(chunk_results, analysis_function)

    async def _analyze_single_chunk(self, i: int, chunk: str, analysis_function: str) -> Optional[Dict[str, Any]]:
        try:
            result = await self.kernel.invoke(
                self.functions[analysis_function],
                input_str=chunk
            )
            
            # Use safe JSON parsing
            parsed_result = self._safe_json_parse(result, f"chunk_analysis_{analysis_function}")
            if not parsed_result:
                return None
            if parsed_result.get('event_found', False) or parsed_result.get('is_relevant', False):
                return {
                    'chunk_index': i,
                    'chunk_text': chunk[:200] + "..." if len(chunk) > 200 else chunk,
                    'result': parsed_result,
                    'key_terms': self._extract_key_terms(chunk)
                }
        except Exception as e:
            print(f"⚠️  Error analyzing chunk {i}: {e}")
        return None

    def _synthesize_chunk_results(self, chunk_results: List[Dict[str, Any]], analysis_type: str) -> List[Dict[str, Any]]:
        """
        Synthesize results from multiple chunks into a coherent analysis.
        """
        if not chunk_results:
            return []
        
        # For certain types, consider all relevant results, not just first
        if analysis_type in ['procurement', 'earnings']:
            # Return all relevant results instead of just the first
            return [result['result'] for result in chunk_results if result['result'].get('event_found', False)]
        else:
            # For other types, keep current behavior
            return [chunk_results[0]['result']] if chunk_results else []

    def _safe_json_parse(self, result, context="unknown") -> Optional[Dict]:
        """Safely parse JSON from various result types."""
        content = None
        
        if hasattr(result, 'content'):
            content = result.content
        elif hasattr(result, 'inner_content'):
            content = result.inner_content
        else:
            content = str(result)
        
        if not content:
            print(f"⚠️  Empty content for JSON parsing in {context}")
            return None
        
        try:
            # Validate content length
            if len(content) > 1_000_000:  # 1MB limit
                print(f"❌ JSON content too large in {context}")
                return None
            
            parsed = json.loads(content)
            
            # Validate structure
            if not isinstance(parsed, dict):
                print(f"❌ JSON is not a dictionary in {context}")
                return None
            
            return parsed
        
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error in {context}: {e}")
            print(f"📋 Problematic content: {content[:200]}...")
            return None
        except Exception as e:
            print(f"❌ Unexpected error parsing JSON in {context}: {e}")
            return None

    async def triage_data(self, data_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Triage data to filter out irrelevant items using intelligent text processing."""
        await self._ensure_kernel_initialized()
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
                    result = await self.kernel.invoke(
                        self.functions['triage'],
                        input_str=text
                    )
                    
                    # Use safe JSON parsing
                    triage_result = self._safe_json_parse(result, "triage_analysis")
                    if triage_result and triage_result.get('is_relevant', False):
                        item['triage_result'] = triage_result
                        relevant_items.append(item)
                else:
                    # For long texts, use intelligent chunking
                    chunks = self._create_intelligent_chunks(text)
                    prioritized_chunks = self._prioritize_chunks(chunks)[:3]  # Analyze top 3 chunks for triage
                    
                    # Analyze each prioritized chunk
                    for chunk in prioritized_chunks:
                        result = await self.kernel.invoke(
                            self.functions['triage'],
                            input_str=chunk
                        )
                        
                        # Use safe JSON parsing
                        triage_result = self._safe_json_parse(result, "triage_chunk_analysis")
                        if triage_result and triage_result.get('is_relevant', False):
                            item['triage_result'] = triage_result
                            item['analyzed_chunks'] = len(chunks)
                            relevant_items.append(item)
                            print(f"✅ Found relevant content in {len(chunks)}-chunk document")
                            break
                    
            except Exception as e:
                print(f"Error during triage for item: {e}")
                continue
        
        print(f"Triage complete: {len(relevant_items)} relevant items found out of {len(data_items)}")
        return relevant_items

    async def analyze_financial_events(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze items for financial events using intelligent chunking."""
        await self._ensure_kernel_initialized()
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
                        result = await self.kernel.invoke(
                            self.functions['financial'],
                            input_str=text
                        )
                        
                        financial_result = self._safe_json_parse(result, "financial_analysis")
                        if financial_result and financial_result.get('event_found', False):
                            value_usd = financial_result.get('value_usd', 0)
                            if value_usd is not None and value_usd >= 10_000_000:
                                item['financial_analysis'] = financial_result
                                financial_events.append(item)
                    else:
                        # Long text - use map-reduce pattern
                        chunks = self._create_intelligent_chunks(text)
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'financial')
                        
                        if chunk_results:
                            # Use the synthesized result
                            synthesized = chunk_results[0]
                            if synthesized['synthesized_result'].get('event_found', False):
                                value_usd = synthesized['synthesized_result'].get('value_usd', 0)
                                if value_usd is not None and value_usd >= 10_000_000:
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
        await self._ensure_kernel_initialized()
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
                        result = await self.kernel.invoke(
                            self.functions['procurement'],
                            input_str=text
                        )
                        
                        procurement_result = self._safe_json_parse(result, "procurement_analysis")
                        if procurement_result and procurement_result.get('is_relevant', False):
                            value_usd = procurement_result.get('value_usd', 0)
                            if value_usd is not None and value_usd >= 10_000_000:
                                item['procurement_analysis'] = procurement_result
                                procurement_events.append(item)
                    else:
                        # Long text - use map-reduce pattern
                        chunks = self._create_intelligent_chunks(text)
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'procurement')
                        
                        if chunk_results:
                            # Use the synthesized result
                            synthesized = chunk_results[0]
                            if synthesized['synthesized_result'].get('is_relevant', False):
                                value_usd = synthesized['synthesized_result'].get('value_usd', 0)
                                if value_usd is not None and value_usd >= 10_000_000:
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
        await self._ensure_kernel_initialized()
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
                        result = await self.kernel.invoke(
                            self.functions['earnings'],
                            input_str=text
                        )
                        
                        earnings_result = self._safe_json_parse(result, "earnings_analysis")
                        if earnings_result and earnings_result.get('guidance_found', False):
                            value_usd = earnings_result.get('value_usd', 0)
                            if value_usd is not None and value_usd >= 10_000_000:
                                item['earnings_analysis'] = earnings_result
                                earnings_events.append(item)
                    else:
                        # Long text - use map-reduce pattern
                        chunks = self._create_intelligent_chunks(text)
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'earnings')
                        
                        if chunk_results:
                            # Use the synthesized result
                            synthesized = chunk_results[0]
                            if synthesized['synthesized_result'].get('guidance_found', False):
                                value_usd = synthesized['synthesized_result'].get('value_usd', 0)
                                if value_usd is not None and value_usd >= 10_000_000:
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
        await self._ensure_kernel_initialized()
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
                result = await self.kernel.invoke(
                    self.functions['insight'],
                    input_str=json.dumps(insight_data)
                )
                
                # Parse result safely
                insight_result = self._safe_json_parse(result, "insight_generation")
                if insight_result:
                    event['insights'] = insight_result
                    insights.append(event)
                else:
                    print(f"Warning: Could not parse insight for event: {event.get('title', 'Unknown')}")
                    
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