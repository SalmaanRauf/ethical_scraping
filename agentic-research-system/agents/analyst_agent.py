import json
import asyncio
import re
import os
from typing import List, Dict, Any, Optional
from config.kernel_setup import get_kernel, get_kernel_async
from semantic_kernel.functions import KernelFunctionFromPrompt
from semantic_kernel.kernel import KernelArguments
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.text_content import TextContent
from dataclasses import dataclass
from semantic_kernel.functions.kernel_arguments import KernelArguments
import traceback
from pathlib import Path

class AnalystAgent:
    def __init__(self, chunk_size: int = 3000, chunk_overlap: int = 500, max_chunks: int = 10):
        try:
            self.kernel, self.exec_settings = get_kernel()
        except RuntimeError:
            self.kernel = None
            self.exec_settings = None
        self.functions = {}
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunks = max_chunks
        self.company_profiles = {}
        self._load_functions()
        
    def set_profiles(self, profiles_dict: dict):
        self.company_profiles = profiles_dict or {}

    async def _ensure_kernel_initialized(self):
        if self.kernel is None or self.exec_settings is None:
            self.kernel, self.exec_settings = await get_kernel_async()
            self._load_functions()
        
    def _load_functions(self):
        # Always resolve relative to the project root
        project_root = Path(__file__).parent.parent
        sk_dir = project_root / "sk_functions"
        
        prompt_files = {
            "triage": "Triage_CategoryRouting_prompt.txt",
            "financial": "FinancialEvent_Detection_prompt.txt", 
            "procurement": "OpportunityIdent_skprompt.txt",
            "earnings": "EarningsCall_GuidanceAnalysis_prompt.txt",
            "insight": "StrategicInsight_Generation_prompt.txt",
            "company_takeaway": "CompanyTakeaway_skprompt.txt",
        }
        for name, fname in prompt_files.items():
            path = sk_dir / fname
            try:
                with open(path, "r", encoding="utf-8") as f:
                    template = f.read()
                func = KernelFunctionFromPrompt(
                    function_name=name,
                    plugin_name="analyst_plugin",
                    description=f"{name} analysis function",
                    prompt=template
                )
                self.functions[name] = func
                if self.kernel:
                    try:
                        self.kernel.add_function(
                            function=func,
                            plugin_name="analyst_plugin"
                        )
                        print(f"✅ Successfully loaded SK function: {name}")
                    except Exception as ex:
                        print(f"⚠️  Failed to add SK function '{name}': {ex}")
            except FileNotFoundError:
                print(f"❌ Prompt file not found: {path}")
            except Exception as e:
                print(f"❌ Error loading prompt '{name}' from {path}: {e}")
        print(f"✅ Loaded {len(self.functions)} Semantic Kernel functions successfully")

    async def _invoke_function_safely(self, function_name: str, input_text: str):
        try:
            if function_name not in self.functions:
                raise ValueError(f"Function '{function_name}' not found")
            func = self.functions[function_name]
            arguments = KernelArguments(input=input_text)
            prompt_template = getattr(func, "prompt", None)
            if prompt_template:
                try:
                    debug_prompt = prompt_template.replace("{{$input}}", input_text)
                    print(f"\n--- DEBUG: Prompt for SK function '{function_name}' ---")
                    print(debug_prompt[:1500] + ("..." if len(debug_prompt) > 1500 else ""))
                    print("-" * 60)
                except Exception as e:
                    print(f"DEBUG: Could not render debug prompt: {e}")
            result = await self.kernel.invoke(
                function_name=function_name,
                plugin_name="analyst_plugin",
                arguments=arguments
            )
            return result
        except Exception as e:
            print(f"❌ Error invoking function '{function_name}': {e}")
            traceback.print_exc()
            return None

    def _create_intelligent_chunks(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        if not text:
            return []
        if len(text) > 10_000_000:
            print(f"⚠️  Text too large ({len(text)} chars), truncating to 10MB")
            text = text[:10_000_000]
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.chunk_overlap
        if len(text) <= chunk_size:
            return [text]
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
            if process and len(chunks) % 10 == 0:
                current_memory = process.memory_info().rss
                if current_memory - initial_memory > 500_000_000:
                    print("⚠️  Memory usage too high, stopping chunk creation")
                    break
            end = start + chunk_size
            if end < len(text):
                search_start = max(start + chunk_size - 200, start)
                search_end = min(start + chunk_size + 200, len(text))
                best_break = end
                for i in range(search_start, search_end):
                    if text[i] in '.!?':
                        if i + 1 < len(text) and text[i + 1] in ' \n\t':
                            if i + 2 < len(text) and text[i + 2].isupper():
                                best_break = i + 1
                                break
                end = best_break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap
            if start >= len(text):
                break
        return chunks

    def _extract_key_terms(self, text: str) -> List[str]:
        key_patterns = [
            r'\$\s*[0-9,.]+(?:\s*(?:million|billion|thousand|m|bn|k))?',
            r'\b(?:Capital One|Fannie Mae|Freddie Mac|Navy Federal|PenFed|EagleBank|Capital Bank)\b',
            r'\b(?:investment|acquisition|merger|partnership|funding|contract|deal|agreement)\b',
            r'\b(?:announces|launches|completes|signs|reports|discloses)\b'
        ]
        key_terms = []
        for pattern in key_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            key_terms.extend(matches)
        return list(set(key_terms))

    def _prioritize_chunks(self, chunks: List[str]) -> List[str]:
        if not chunks:
            return []
        chunk_scores = []
        for i, chunk in enumerate(chunks):
            score = 0
            key_terms = self._extract_key_terms(chunk)
            score += len(key_terms) * 10
            if re.search(r'\$\s*[0-9,.]+', chunk):
                score += 50
            if re.search(r'\b(?:Capital One|Fannie Mae|Freddie Mac|Navy Federal|PenFed|EagleBank|Capital Bank)\b', chunk, re.IGNORECASE):
                score += 30
            if re.search(r'\b(?:announces|launches|completes|signs|reports|discloses)\b', chunk, re.IGNORECASE):
                score += 20
            chunk_scores.append((score, i, chunk))
        chunk_scores.sort(reverse=True)
        return [chunk for _, _, chunk in chunk_scores]

    async def _analyze_chunks_with_map_reduce(self, chunks: List[str], analysis_function: str, max_chunks: int = None) -> List[Dict[str, Any]]:
        if not chunks:
            return []
        max_chunks = max_chunks or self.max_chunks
        prioritized_chunks = self._prioritize_chunks(chunks)[:max_chunks]
        print(f"🔍 Analyzing {len(prioritized_chunks)} prioritized chunks (from {len(chunks)} total)")
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
            result = await self._invoke_function_safely(analysis_function, chunk)
            if result is None:
                return None
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
        if not chunk_results:
            return []
        if analysis_type in ['procurement', 'earnings']:
            return [result['result'] for result in chunk_results if result['result'].get('event_found', False)]
        else:
            return [chunk_results[0]['result']] if chunk_results else []

    def _safe_json_parse(self, result, context="unknown") -> Optional[Dict]:
        import re
        try:
            from semantic_kernel.functions.function_result import FunctionResult
        except ImportError:
            FunctionResult = None
        if FunctionResult and isinstance(result, FunctionResult):
            result = result.value
        if isinstance(result, list):
            for entry in result:
                parsed = self._safe_json_parse(entry, context)
                if parsed is not None:
                    return parsed
            return None
        if hasattr(result, "content") and isinstance(result.content, str):
            content = result.content
        elif hasattr(result, "inner_content"):
            inner_result = result.inner_content
            if hasattr(inner_result, "choices") and hasattr(inner_result.choices[0], "message") and hasattr(inner_result.choices[0].message, "content"):
                content = inner_result.choices[0].message.content
            elif hasattr(inner_result, "content"):
                content = inner_result.content
            else:
                content = str(inner_result)
        elif hasattr(result, "choices") and hasattr(result.choices[0], "message") and hasattr(result.choices[0].message, "content"):
            content = result.choices[0].message.content
        elif hasattr(result, "value"):
            content = str(result.value)
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)
        if not content:
            print(f"⚠️  Empty content for JSON parsing in {context}")
            return None
        content = content.strip()
        if content.startswith('```json'):
            content = content[len('```json'):].strip()
        if content.startswith('```'):
            content = content[len('```'):].strip()
        if content.endswith('```'):
            content = content[:-3].strip()
        content = re.sub(r'^(json|CopyEdit|Edit)?\\s*', '', content)
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                print(f"❌ JSON is not a dictionary in {context}")
                return None
            return parsed
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error in {context}: {e}")
            print(f"📋 Problematic content: {content[:500]}...")
            return None
        except Exception as e:
            print(f"❌ Unexpected error parsing JSON in {context}: {e}")
            return None

    async def analyze_consolidated_data(self, events_input, analysis_document: str) -> List[Dict[str, Any]]:
        if isinstance(events_input, dict) and "events" in events_input and "profiles" in events_input:
            events = events_input["events"]
            profiles = events_input["profiles"]
        else:
            events = events_input
            profiles = getattr(self, "company_profiles", {})
        self.company_profiles = profiles
        print(f"\U0001F9E0 Starting analysis of {len(events)} consolidated items...")
        adapted_data = []
        for item in events:
            raw_data = item.get('raw_data', {})
            adapted_item = {
                'title': item.get('title', raw_data.get('title', '')),
                'description': item.get('content', item.get('description', raw_data.get('description', ''))),  # Use content field from consolidated data
                'company': item.get('company', raw_data.get('company', '')),
                'source': item.get('source_name', raw_data.get('source', '')),
                'url': item.get('url', raw_data.get('link', '')),
                'published_date': item.get('published_date', raw_data.get('date', '')),
                'source_type': item.get('source_type', 'unknown'),
                'key_terms': item.get('key_terms', []),
                'relevance_score': item.get('relevance_score', 0.0)
            }
            source = adapted_item['source'].lower()
            if 'sec' in source:
                adapted_item['type'] = 'news'
                adapted_item['data_type'] = 'filing'
            elif 'sam.gov' in source:
                adapted_item['type'] = 'procurement'
            elif 'news' in source:
                adapted_item['type'] = 'news'
            else:
                adapted_item['type'] = 'unknown'
            if isinstance(raw_data, dict) and 'value_usd' in raw_data:
                adapted_item['value_usd'] = raw_data['value_usd']
            if adapted_item['type'] == 'news':
                adapted_item['summary'] = adapted_item['description']
            elif adapted_item.get('data_type') == 'filing':
                adapted_item['text'] = f"{adapted_item['title']} {adapted_item['description']}"
            adapted_data.append(adapted_item)
        print(f"✅ Adapted {len(adapted_data)} items for analysis")
        results = await self.analyze_all_data(adapted_data)
        print(f"🎯 Analysis complete: {len(results)} events identified")
        return results
    
    async def triage_data(self, data_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        await self._ensure_kernel_initialized()
        relevant_items = []
        
        # Debug: Check chunk_size type
        if not isinstance(self.chunk_size, int):
            print(f"⚠️  WARNING: chunk_size is {type(self.chunk_size)}, resetting to 3000")
            self.chunk_size = 3000
        
        for item in data_items:
            try:
                # Use content field if available, otherwise fall back to description
                text = str(item.get('content', item.get('description', ''))).strip()
                scraped_label = "(SCRAPED)" if item.get('raw_data', {}).get('content_enhanced') else "(SUMMARY_ONLY)"
                print(f"[ANALYST][TRIAGE] Input: '{item.get('title', 'NO TITLE')[:60]}' | Length: {len(text)} | {scraped_label}")
                if not text:
                    print(f"[ANALYST][TRIAGE] Skipping empty content: {item.get('title', 'NO TITLE')[:60]}")
                    continue
                if len(text) <= self.chunk_size:
                    result = await self._invoke_function_safely('triage', text)
                    if result is None:
                        print(f"[ANALYST][TRIAGE] No result for: '{item.get('title', '')[:60]}'")
                        continue
                    triage_result = self._safe_json_parse(result, "triage_analysis")
                    if triage_result and triage_result.get('is_relevant', False):
                        item['triage_result'] = triage_result
                        relevant_items.append(item)
                        print(f"[ANALYST][TRIAGE] Relevant: '{item.get('title', '')[:60]}'")
                    else:
                        # Debug: Show why items are being filtered out
                        category = triage_result.get('category', 'Unknown') if triage_result else 'No result'
                        reasoning = triage_result.get('reasoning', 'No reasoning') if triage_result else 'No result'
                        print(f"[ANALYST][TRIAGE] Filtered out: '{item.get('title', '')[:60]}' | Category: {category} | Reason: {reasoning}")
                else:
                    chunks = self._create_intelligent_chunks(text)
                    prioritized_chunks = self._prioritize_chunks(chunks)[:3]
                    for chunk in prioritized_chunks:
                        result = await self._invoke_function_safely('triage', chunk)
                        if result is None:
                            continue
                        triage_result = self._safe_json_parse(result, "triage_chunk_analysis")
                        if triage_result and triage_result.get('is_relevant', False):
                            item['triage_result'] = triage_result
                            item['analyzed_chunks'] = len(chunks)
                            relevant_items.append(item)
                            print(f"[ANALYST][TRIAGE] Relevant chunk found for: {item.get('title', '')[:60]}")
                            break
                        else:
                            # Debug: Show why chunks are being filtered out
                            category = triage_result.get('category', 'Unknown') if triage_result else 'No result'
                            reasoning = triage_result.get('reasoning', 'No reasoning') if triage_result else 'No result'
                            print(f"[ANALYST][TRIAGE] Chunk filtered out: '{item.get('title', '')[:60]}' | Category: {category} | Reason: {reasoning}")
            except Exception as e:
                print(f"Error during triage for item: {e}")
                continue
        print(f"Triage complete: {len(relevant_items)} relevant items found out of {len(data_items)}")
        return relevant_items

    async def analyze_financial_events(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        await self._ensure_kernel_initialized()
        financial_events = []
        
        # Debug: Check chunk_size type
        if not isinstance(self.chunk_size, int):
            print(f"⚠️  WARNING: chunk_size is {type(self.chunk_size)}, resetting to 3000")
            self.chunk_size = 3000
        
        for item in items:
            # Process all items that passed triage, not just specific categories
            if item.get('triage_result', {}).get('is_relevant', False):
                try:
                    # Use content field if available, otherwise fall back to description
                    text = str(item.get('content', item.get('description', ''))).strip()
                    scraped_label = "(SCRAPED)" if item.get('raw_data', {}).get('content_enhanced') else "(SUMMARY_ONLY)"
                    print(f"[ANALYST][FINANCIAL] Processing: '{item.get('title', '')[:60]}' | Length: {len(text)} | {scraped_label}")
                    if not text:
                        continue
                    if len(text) <= self.chunk_size:
                        result = await self._invoke_function_safely('financial', text)
                        if result is None:
                            print(f"[ANALYST][FINANCIAL] No result: '{item.get('title', '')[:60]}'")
                            continue
                        financial_result = self._safe_json_parse(result, "financial_analysis")
                        if financial_result and financial_result.get('event_found', False):
                            value_usd = financial_result.get('value_usd', 0)
                            event_type = financial_result.get('event_type', '')
                            
                            # Only require $10M for specific event types that have monetary thresholds
                            monetary_event_types = ['M&A', 'Funding', 'Investment', 'Technology']
                            if event_type in monetary_event_types and value_usd is not None:
                                if value_usd >= 10_000_000:
                                    item['financial_analysis'] = financial_result
                                    financial_events.append(item)
                                    print(f"[ANALYST][FINANCIAL] Event >=$10M: '{item.get('title', '')[:60]}' (${value_usd:,})")
                            else:
                                # For non-monetary events (regulatory, operational, etc.), include regardless of value
                                item['financial_analysis'] = financial_result
                                financial_events.append(item)
                                print(f"[ANALYST][FINANCIAL] Non-monetary event: '{item.get('title', '')[:60]}' ({event_type})")
                    else:
                        chunks = self._create_intelligent_chunks(text)
                        print(f"[ANALYST][FINANCIAL] {len(chunks)} chunks for: '{item.get('title', '')[:60]}'")
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'financial')
                        if chunk_results:
                            synthesized = chunk_results[0]
                            if synthesized.get('event_found', False):
                                value_usd = synthesized.get('value_usd', 0)
                                event_type = synthesized.get('event_type', '')
                                
                                # Only require $10M for specific event types that have monetary thresholds
                                monetary_event_types = ['M&A', 'Funding', 'Investment', 'Technology']
                                if event_type in monetary_event_types and value_usd is not None:
                                    if value_usd >= 10_000_000:
                                        item['financial_analysis'] = synthesized
                                        item['analysis_metadata'] = {
                                            'chunks_analyzed': len(chunks),
                                            'analysis_method': 'map_reduce'
                                        }
                                        financial_events.append(item)
                                        print(f"[ANALYST][FINANCIAL] Event >=$10M (chunks): '{item.get('title', '')[:60]}' (${value_usd:,})")
                                else:
                                    # For non-monetary events (regulatory, operational, etc.), include regardless of value
                                    item['financial_analysis'] = synthesized
                                    item['analysis_metadata'] = {
                                        'chunks_analyzed': len(chunks),
                                        'analysis_method': 'map_reduce'
                                    }
                                    financial_events.append(item)
                                    print(f"[ANALYST][FINANCIAL] Non-monetary event (chunks): '{item.get('title', '')[:60]}' ({event_type})")
                except Exception as e:
                    print(f"Error during financial analysis: {e}")
                    continue
        print(f"Financial analysis complete: {len(financial_events)} events found")
        return financial_events

    async def analyze_procurement(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        await self._ensure_kernel_initialized()
        procurement_events = []
        
        # Debug: Check chunk_size type
        if not isinstance(self.chunk_size, int):
            print(f"⚠️  WARNING: chunk_size is {type(self.chunk_size)}, resetting to 3000")
            self.chunk_size = 3000
        
        for item in items:
            if item.get('triage_result', {}).get('category') == 'Procurement Notice':
                try:
                    # Use content field if available, otherwise fall back to description
                    text = str(item.get('content', item.get('description', ''))).strip()
                    scraped_label = "(SCRAPED)" if item.get('raw_data', {}).get('content_enhanced') else "(SUMMARY_ONLY)"
                    print(f"[ANALYST][PROCUREMENT] Processing: '{item.get('title', '')[:60]}' | Length: {len(text)} | {scraped_label}")
                    if not text:
                        continue
                    if len(text) <= self.chunk_size:
                        result = await self._invoke_function_safely('procurement', text)
                        if result is None:
                            print(f"[ANALYST][PROCUREMENT] No result: '{item.get('title', '')[:60]}'")
                            continue
                        procurement_result = self._safe_json_parse(result, "procurement_analysis")
                        if procurement_result and procurement_result.get('is_relevant', False):
                            value_usd = procurement_result.get('value_usd', 0)
                            # Include all relevant procurement events, regardless of value
                            item['procurement_analysis'] = procurement_result
                            procurement_events.append(item)
                            if value_usd and value_usd >= 10_000_000:
                                print(f"[ANALYST][PROCUREMENT] Relevant procurement >=$10M: '{item.get('title', '')[:60]}' (${value_usd:,})")
                            else:
                                print(f"[ANALYST][PROCUREMENT] Relevant procurement: '{item.get('title', '')[:60]}' (value: ${value_usd:, if value_usd else 'N/A'})")
                    else:
                        chunks = self._create_intelligent_chunks(text)
                        print(f"[ANALYST][PROCUREMENT] {len(chunks)} chunks for: '{item.get('title', '')[:60]}'")
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'procurement')
                        if chunk_results:
                            synthesized = chunk_results[0]
                            if synthesized.get('is_relevant', False):
                                value_usd = synthesized.get('value_usd', 0)
                                # Include all relevant procurement events, regardless of value
                                item['procurement_analysis'] = synthesized
                                item['analysis_metadata'] = {
                                    'chunks_analyzed': len(chunks),
                                    'analysis_method': 'map_reduce'
                                }
                                procurement_events.append(item)
                                if value_usd and value_usd >= 10_000_000:
                                    print(f"[ANALYST][PROCUREMENT] Relevant procurement >=$10M (chunks): '{item.get('title', '')[:60]}' (${value_usd:,})")
                                else:
                                    print(f"[ANALYST][PROCUREMENT] Relevant procurement (chunks): '{item.get('title', '')[:60]}' (value: ${value_usd:, if value_usd else 'N/A'})")
                except Exception as e:
                    print(f"Error during procurement analysis: {e}")
                    continue
        print(f"Procurement analysis complete: {len(procurement_events)} relevant notices found")
        return procurement_events

    async def analyze_earnings_calls(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        await self._ensure_kernel_initialized()
        earnings_events = []
        
        # Debug: Check chunk_size type
        if not isinstance(self.chunk_size, int):
            print(f"⚠️  WARNING: chunk_size is {type(self.chunk_size)}, resetting to 3000")
            self.chunk_size = 3000
        
        for item in items:
            if item.get('triage_result', {}).get('category') == 'Earnings Call':
                try:
                    # Use content field if available, otherwise fall back to description
                    text = str(item.get('content', item.get('description', ''))).strip()
                    scraped_label = "(SCRAPED)" if item.get('raw_data', {}).get('content_enhanced') else "(SUMMARY_ONLY)"
                    print(f"[ANALYST][EARNINGS] Processing: '{item.get('title', '')[:60]}' | Length: {len(text)} | {scraped_label}")
                    if not text:
                        continue
                    if len(text) <= self.chunk_size:
                        result = await self._invoke_function_safely('earnings', text)
                        if result is None:
                            print(f"[ANALYST][EARNINGS] No result: '{item.get('title', '')[:60]}'")
                            continue
                        earnings_result = self._safe_json_parse(result, "earnings_analysis")
                        if earnings_result and earnings_result.get('guidance_found', False):
                            value_usd = earnings_result.get('value_usd', 0)
                            # Include all relevant earnings guidance, regardless of value
                            item['earnings_analysis'] = earnings_result
                            earnings_events.append(item)
                            if value_usd and value_usd >= 10_000_000:
                                print(f"[ANALYST][EARNINGS] Earnings guidance >=$10M: '{item.get('title', '')[:60]}' (${value_usd:,})")
                            else:
                                print(f"[ANALYST][EARNINGS] Earnings guidance: '{item.get('title', '')[:60]}' (value: ${value_usd:, if value_usd else 'N/A'})")
                    else:
                        chunks = self._create_intelligent_chunks(text)
                        print(f"[ANALYST][EARNINGS] {len(chunks)} chunks for: '{item.get('title', '')[:60]}'")
                        chunk_results = await self._analyze_chunks_with_map_reduce(chunks, 'earnings')
                        if chunk_results:
                            synthesized = chunk_results[0]
                            if synthesized.get('guidance_found', False):
                                value_usd = synthesized.get('value_usd', 0)
                                # Include all relevant earnings guidance, regardless of value
                                item['earnings_analysis'] = synthesized
                                item['analysis_metadata'] = {
                                    'chunks_analyzed': len(chunks),
                                    'analysis_method': 'map_reduce'
                                }
                                earnings_events.append(item)
                                if value_usd and value_usd >= 10_000_000:
                                    print(f"[ANALYST][EARNINGS] Earnings guidance >=$10M (chunks): '{item.get('title', '')[:60]}' (${value_usd:,})")
                                else:
                                    print(f"[ANALYST][EARNINGS] Earnings guidance (chunks): '{item.get('title', '')[:60]}' (value: ${value_usd:, if value_usd else 'N/A'})")
                except Exception as e:
                    print(f"Error during earnings call analysis: {e}")
                    continue
        print(f"Earnings call analysis complete: {len(earnings_events)} guidance items found")
        return earnings_events

    async def generate_insights(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate insights for all events. Company profile, buyers, projects, and alumni are now factored in.
        """
        await self._ensure_kernel_initialized()
        insights = []
        for event in events:
            try:
                company_profile = self.company_profiles.get(event.get('company', ''), {})
                insight_data = {
                    'company': event.get('company', ''),
                    'title': event.get('title', ''),
                    'source': event.get('source', ''),
                    'type': event.get('type', ''),
                    'company_profile': company_profile,
                    'key_buyers': company_profile.get('key_buyers', []),
                    'projects': company_profile.get('projects', []),
                    'protiviti_alumni': company_profile.get('protiviti_alumni', []),
                }
                if 'financial_analysis' in event:
                    insight_data.update(event['financial_analysis'])
                elif 'procurement_analysis' in event:
                    insight_data.update(event['procurement_analysis'])
                elif 'earnings_analysis' in event:
                    insight_data.update(event['earnings_analysis'])
                result = await self._invoke_function_safely('insight', json.dumps(insight_data))
                if result is None:
                    continue
                insight_result = self._safe_json_parse(result, "insight_generation")
                if insight_result:
                    event['insights'] = insight_result
                    insights.append(event)
                else:
                    print(f"Warning: Could not parse insight for event: {event.get('title', 'Unknown')}")
            except Exception as e:
                print(f"Error generating insight: {e}")
                continue
        from collections import defaultdict
        company_map = defaultdict(list)
        for ev in insights:
            company_map[ev['company']].append(ev)
        for company, evts in company_map.items():
            profile = self.company_profiles.get(company, {})
            summary_input = {
                'company': company,
                'profile': profile,
                'events': [{
                    'title': e['title'], 'insights': e.get('insights', {})
                } for e in evts]
            }
            summary_json = json.dumps(summary_input)
            summary = await self._invoke_function_safely('company_takeaway', summary_json)
            for e in evts:
                e['company_takeaway'] = summary
        print(f"Insight generation complete: {len(insights)} insights generated")
        return insights

    async def analyze_all_data(self, data_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print(f"Starting analysis of {len(data_items)} data items...")
        relevant_items = await self.triage_data(data_items)
        financial_events = await self.analyze_financial_events(relevant_items)
        procurement_events = await self.analyze_procurement(relevant_items)
        earnings_events = await self.analyze_earnings_calls(relevant_items)
        all_events = financial_events + procurement_events + earnings_events
        final_insights = await self.generate_insights(all_events)
        print(f"Analysis complete: {len(final_insights)} high-impact events identified")
        return final_insights

if __name__ == "__main__":
    import asyncio
    class DummySelf(AnalystAgent):
        async def _ensure_kernel_initialized(self): pass
        async def _invoke_function_safely(self, name, payload):
            if name == 'insight':
                return '{"what_happened": "Event:", "why_it_matters": "Matters.", "consulting_angle": "Sell", "priority": "high", "timeline": "immediate", "service_categories": ["Advisory"]}'
            elif name == 'company_takeaway':
                return '{"summary": "Use buyers and alumni on new project. Upsell opportunities: risk management."}'
    agent = DummySelf()
    agent.company_profiles = {
        'Capital One': {
            'key_buyers': [{"name": "Jane Buyer"}],
            'projects': [{"name": "Audit2023"}],
            'protiviti_alumni': [{"name": "Al Smith"}]
        }
    }
    sample = [{
        'company': 'Capital One',
        'title': 'Event X'
    }]
    out = asyncio.run(agent.generate_insights(sample))
    assert 'company_takeaway' in out[0] and 'summary' in out[0]['company_takeaway']
    print("✅ AnalystAgent company_takeaway injection test passed.")
