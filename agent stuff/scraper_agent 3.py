import asyncio
import logging
import time
import random
import re
from typing import Optional, Dict, List
from urllib.parse import urlparse, parse_qs, unquote
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from extractors.http_utils import USER_AGENTS, can_fetch
import newspaper
from trafilatura import extract as trafilatura_extract
from bs4 import BeautifulSoup
from readability import Document
from json import loads

try:
    from playwright.async_api import async_playwright, Browser, Playwright
    from playwright_stealth import stealth_async
except ImportError:
    async_playwright = None
    stealth_async = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ScraperAgent:
    """
    Attempts robust, ethical article extraction via a multi-step pipeline:
    1. Try Trafilatura, Newspaper3k, BeautifulSoup (fast, synchronous)
    2. If those fail, use Playwright with stealth mode and Readability fallback.
    Handles rate limiting, robots.txt, redirects, retries, and logging.
    Special handling for sites (like MSN) with dynamic/JS content and JSON-LD Article.
    """

    def __init__(self):
        self.session = self._setup_session()
        self.user_agents = USER_AGENTS.copy()
        self.last_request_times: Dict[str, float] = {}
        self.min_interval = 1.5  # seconds between requests per domain
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._sem = asyncio.Semaphore(3)
        # MSN-specific selectors, easily extendable
        self.msn_selectors = [
            'div[itemprop="articleBody"]',
            'div[data-module="ArticleBody"]',
            'div.articlebody',
            'div.article-body',
            'div.story-body',
            'div.content-body',
            'div.post-content',
            'div.entry-content',
            'div[class*="article-content"]',
            'div[class*="story-content"]',
            'main article',
            'section[role="main"]'
        ]
        logger.info("✅ ScraperAgent initialized")

    def is_available(self):
        """
        Indicates that the ScraperAgent is available for use.
        This method always returns True and exists solely for API compatibility
        with code that checks for 'is_available' on the scraper_agent instance.
        """
        return True

    def _setup_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=4,  # More retries for robustness
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _rate_limit_sync(self, domain: str):
        interval = 0.8 if 'msn.com' in domain else self.min_interval
        now = time.time()
        last = self.last_request_times.get(domain, 0)
        wait = interval - (now - last)
        if wait > 0:
            logger.debug(f"[RateLimitSync] Waiting {wait:.2f}s for domain {domain}")
            time.sleep(wait)
        self.last_request_times[domain] = time.time()

    async def _rate_limit_async(self, domain: str):
        interval = 0.8 if 'msn.com' in domain else self.min_interval
        now = time.time()
        last = self.last_request_times.get(domain, 0)
        wait = interval - (now - last)
        if wait > 0:
            logger.debug(f"[RateLimitAsync] Waiting {wait:.2f}s for domain {domain}")
            await asyncio.sleep(wait)
        self.last_request_times[domain] = time.time()

    def _get_headers(self, for_msn: bool = False) -> Dict[str, str]:
        # Enhanced headers for MSN with more realistic browser fingerprint
        base_headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if for_msn:
            base_headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Dnt": "1",
            })
        return base_headers

    def _resolve_redirects(self, url: str) -> str:
        """
        Enhanced aggregator redirect logic:
        - If Bing/MSN/Google/Yahoo aggregator: Only handle one redirect, or extract target URL from param.
        - Never let MSN's own redirect boot you to the homepage.
        - Pass through for non-aggregators.
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        agg_patterns = ("bing.com/news/apiclick", "news.google.", "yahoo.com/news/rss")
        # Prefer extracting from query param for aggregator links
        if any(agg in url for agg in agg_patterns):
            try:
                qs = parse_qs(parsed.query)
                real_url = unquote(qs.get("url", [""])[0])
                if real_url:
                    logger.info(f"[Aggregator] Parsed aggregator URL param: {url} -> {real_url}")
                    return real_url
            except Exception as e:
                logger.warning(f"[Aggregator] Could not extract target from aggregator: {e}")

        try:
            is_msn = 'msn.com' in domain
            resp = self.session.get(url, headers=self._get_headers(for_msn=is_msn), timeout=15, allow_redirects=False)
            location = resp.headers.get('Location')
            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                if location and location not in ('/', 'https://www.msn.com/', url):
                    logger.info(f"[RedirectStep] Manual (single-hop) redirect: {url} -> {location}")
                    return location
                else:
                    logger.warning(f"[RedirectStep] Redirect leads to homepage or loop: {url} -> {location}")
        except Exception as e:
            logger.warning(f"[RedirectStep] Manual redirect error: {e}")
        return url

    def _method_trafilatura(self, url: str) -> Optional[str]:
        domain = urlparse(url).netloc
        self._rate_limit_sync(domain)
        try:
            is_msn = 'msn.com' in domain
            resp = self.session.get(url, headers=self._get_headers(for_msn=is_msn), timeout=20)
            logger.debug(f"[Trafilatura] {url} HTTP {resp.status_code}, RespLen={len(resp.text)}")
            if resp.status_code == 200:
                txt = trafilatura_extract(resp.text,
                                          include_comments=False,
                                          include_tables=True,  # MSN sometimes uses tables
                                          include_formatting=False,
                                          favor_precision=True,
                                          include_links=False)
                logger.debug(f"[Trafilatura] Output len: {len(txt) if txt else 0}")
                if txt and len(txt) > 200:
                    logger.info(f"✅ Trafilatura ({len(txt)} chars)")
                    return txt
                else:
                    logger.debug(f"[Trafilatura] Extraction too short or empty.")
        except Exception as e:
            logger.debug(f"[Trafilatura error] {e}", exc_info=True)
        return None

    def _method_newspaper(self, url: str) -> Optional[str]:
        domain = urlparse(url).netloc
        self._rate_limit_sync(domain)
        try:
            config = newspaper.Config()
            config.browser_user_agent = random.choice(self.user_agents)
            config.request_timeout = 20
            config.number_threads = 1
            article = newspaper.Article(url, config=config)
            article.download()
            article.parse()
            txt = article.text
            logger.debug(f"[Newspaper3k] Output len: {len(txt) if txt else 0}")
            if txt and len(txt) > 200:
                logger.info(f"✅ Newspaper3k ({len(txt)} chars)")
                return txt
            else:
                logger.debug("[Newspaper3k] Extraction too short or empty.")
        except Exception as e:
            logger.debug(f"[Newspaper3k error] {e}", exc_info=True)
        return None

    def _method_bs4(self, url: str) -> Optional[str]:
        domain = urlparse(url).netloc
        self._rate_limit_sync(domain)
        try:
            is_msn = 'msn.com' in domain
            is_sec = 'sec.gov' in domain and '/edgar/' in url
            resp = self.session.get(url, headers=self._get_headers(for_msn=is_msn), timeout=20)
            logger.debug(f"[BS4] {url} HTTP {resp.status_code}, RespLen={len(resp.text)}")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                # SEC-specific extraction
                if is_sec:
                    # Try narrative blocks
                    form_content = soup.find('div', class_='formContent')
                    if form_content:
                        txt = form_content.get_text(separator='\n').strip()
                        if len(txt) > 200:
                            logger.info(f"✅ SEC formContent block ({len(txt)} chars)")
                            return txt
                    # Try all <pre> blocks (some filings are in <pre>)
                    pre_blocks = soup.find_all('pre')
                    pre_texts = []
                    for pre in pre_blocks:
                        t = pre.get_text(separator='\n').strip()
                        if t and len(t) > 200:
                            pre_texts.append(t)
                    if pre_texts:
                        longest = max(pre_texts, key=len)
                        logger.info(f"✅ SEC <pre> block ({len(longest)} chars)")
                        return longest

                # ----- existing logic below for news/MSN -----
                if is_msn:
                    json_content = self._extract_json_ld(soup)
                    if json_content and len(json_content) > 200:
                        logger.info(f"✅ BS4 JSON-LD ({len(json_content)} chars)")
                        return json_content
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
                    tag.decompose()
                selectors = self.msn_selectors if is_msn else ["article", "[role=main]", "main", ".post-content", ".entry-content"]
                for sel in selectors:
                    el = soup.select_one(sel)
                    if el:
                        txt = el.get_text(separator="\n").strip()
                        logger.debug(f"[BS4] Selector {sel} OutputLen={len(txt)}")
                        if len(txt) > 200:
                            logger.info(f"✅ BS4 selector `{sel}` ({len(txt)} chars)")
                            return txt
                ps = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 50]
                if ps:
                    txt = "\n\n".join(ps)
                    logger.info(f"✅ BS4 paragraphs ({len(txt)} chars)")
                    return txt
                logger.debug(f"[BS4] No suitable selector or paragraphs found.")
        except Exception as e:
            logger.debug(f"[BS4 error] {e}", exc_info=True)
        return None

    def _get_sec_gov_raw_text(self, url: str) -> Optional[str]:
        """
        Fetch the full plain-text version of an EDGAR filing by swapping .htm → .txt.
        """
        txt_url = url.rsplit('.', 1)[0] + '.txt'
        try:
            logger.info(f"[SEC.gov TXT] Fetching raw text from {txt_url}")
            resp = self.session.get(txt_url, headers=self._get_headers(), timeout=30)
            resp.raise_for_status()
            if resp.text and len(resp.text) > 200:
                logger.info(f"[SEC.gov TXT] Retrieved {len(resp.text)} chars")
                return resp.text
            logger.warning(f"[SEC.gov TXT] Too short: {len(resp.text)} chars")
        except Exception as e:
            logger.error(f"[SEC.gov TXT] Error fetching {txt_url}: {e}")
        return None

    def _get_secapi_filing_content(self, url: str) -> Optional[str]:
        """
        Try sec-api.io first; on failure or missing key/regex match, fall back to .txt.
        """
        sec_api_key = os.getenv("SEC_API_KEY")
        # Correct regex: one backslash!
        match = re.search(r"edgar/data/(\d+)/(\d+)[^/]*\.htm", url)
        if not sec_api_key or not match:
            if not sec_api_key:
                logger.warning("SEC_API_KEY not set; falling back to .txt")
            else:
                logger.warning(f"Could not parse CIK/accession from URL: {url}")
            return self._get_sec_gov_raw_text(url)
        cik, accession = match.groups()
        api_url = f"https://api.sec-api.io/filing-text?cik={cik}&accessionNo={accession}"
        headers = {"Authorization": sec_api_key}
        try:
            logger.info(f"[SECAPI] Fetching via sec-api: {api_url}")
            r = requests.get(api_url, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            filing_text = data.get("text", "")
            if filing_text and len(filing_text) > 200:
                logger.info(f"[SECAPI] Retrieved {len(filing_text)} chars")
                return filing_text.strip()
            logger.warning(f"[SECAPI] Empty or short; falling back to .txt")
        except Exception as e:
            logger.error(f"[SECAPI] Error retrieving filing: {e}, falling back to .txt")
        # final fallback
        return self._get_sec_gov_raw_text(url)

    async def _ensure_browser(self):
        """Launch Playwright Chromium with enhanced stealth for MSN."""
        if not async_playwright:
            raise RuntimeError("Playwright not installed")
        if not self._playwright:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-plugins",
                    "--disable-images",
                    "--disable-javascript-harmony-shipping",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-ipc-flooding-protection",
                    "--enable-features=NetworkService,NetworkServiceLogging",
                    "--disable-features=TranslateUI,VizDisplayCompositor",
                ],
            )
            logger.info("🚀 Playwright browser launched with enhanced stealth")

    async def _get_page_with_stealth(self, url: str) -> str:
        async with self._sem:
            await self._ensure_browser()
            await self._rate_limit_async(urlparse(url).netloc)
            is_msn = 'msn.com' in url
            ctx = await self._browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Dnt": "1",
                }
            )
            page = await ctx.new_page()
            if stealth_async:
                await stealth_async(page)
            # Enhanced stealth for MSN
            if is_msn:
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined, });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5], });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'], });
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'permissions', { get: () => ({ query: () => Promise.resolve({ state: 'granted' }), }), });
                """)
            timeout = 60000 if is_msn else 45000
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            logger.debug("[PW] Navigated to URL")
            # Enhanced waiting for MSN
            if is_msn:
                try:
                    await page.wait_for_selector(','.join(self.msn_selectors), timeout=25000)
                    logger.debug("[PW] Found MSN content selector")
                except Exception as e:
                    logger.debug(f"[PW] Could not find MSN content selector: {e}")
                # Human-like mouse, scroll, network idle tricks
                await page.mouse.move(500, 300)
                await asyncio.sleep(0.5)
                await page.mouse.move(800, 600)
                await asyncio.sleep(0.3)
                await page.evaluate("() => { window.scrollTo(0, 200); }")
                await asyncio.sleep(1)
                await page.evaluate("() => { window.scrollTo(0, 500); }")
                await asyncio.sleep(1)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    logger.debug("[PW] Waited for networkidle")
                except Exception as e:
                    logger.debug(f"[PW] networkidle failed: {e}")
                await asyncio.sleep(2)
            else:
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    logger.debug("[PW] Waited for networkidle")
                except Exception as e:
                    logger.debug(f"[PW] networkidle failed: {e}")
            html = await page.content()
            logger.debug(f"[PW] HTML returned, Len={len(html)}")
            await ctx.close()
            return html

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[str]:
        """Enhanced JSON-LD extraction for MSN and other sites."""
        scripts = soup.find_all("script", {"type": "application/ld+json"})
        if not scripts:
            logger.debug("[JSON-LD] No <script type='application/ld+json'> present")
            return None
        for script in scripts:
            if not script.string:
                continue
            try:
                json_str = script.string.strip()
                json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)  # Remove control chars
                data = loads(json_str)
                logger.debug(f"[JSON-LD] Decoded JSON-LD: type={data.get('@type', None) if isinstance(data, dict) else type(data)}")
                content = None
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict) and entry.get("@type") in ("NewsArticle", "Article"):
                            content = entry.get("articleBody") or entry.get("text") or entry.get("description")
                            if content and len(content) > 200:
                                logger.debug(f"[JSON-LD] Found articleBody in list entry len={len(content)}")
                                return content
                elif isinstance(data, dict) and data.get("@type") in ("NewsArticle", "Article"):
                    content = data.get("articleBody") or data.get("text") or data.get("description")
                    if content and len(content) > 200:
                        logger.debug(f"[JSON-LD] Found articleBody in dict len={len(content)}")
                        return content
            except Exception as e:
                logger.debug(f"[JSON-LD parse error: {e}]", exc_info=True)
                continue
        return None

    def _extract_content_with_fallbacks(self, html: str) -> Optional[str]:
        """Enhanced content extraction with MSN-specific fallbacks."""
        soup = BeautifulSoup(html, "html.parser")
        # Try JSON-LD first
        content = self._extract_json_ld(soup)
        if content and len(content) > 200:
            logger.info("✅ Extracted via JSON-LD fallback")
            return content
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "form", "button"]):
            tag.decompose()
        # Try MSN-specific selectors
        is_msn = 'msn.com' in html
        if is_msn:
            for sel in self.msn_selectors:
                el = soup.select_one(sel)
                logger.debug(f"[Fallbacks] MSN selector: {sel} element found: {el is not None}")
                if el:
                    txt = el.get_text(separator="\n").strip()
                    logger.debug(f"[Fallbacks] MSN Selector {sel} text length: {len(txt)}")
                    if len(txt) > 300:
                        logger.info(f"✅ MSN selector `{sel}` ({len(txt)} chars)")
                        return txt
        # Try main content selectors
        for sel in ["article", "[role=main]", "main", ".post-content", ".entry-content"]:
            el = soup.select_one(sel)
            logger.debug(f"[Fallbacks] selector: {sel} element found: {el is not None}")
            if el:
                txt = el.get_text(separator="\n").strip()
                logger.debug(f"[Fallbacks] Selector {sel} text length: {len(txt)}")
                if len(txt) > 300:
                    logger.info(f"✅ BS4 selector `{sel}` ({len(txt)} chars)")
                    return txt
        # Try largest meaningful text blocks
        blocks = []
        for tag in soup.find_all(["div", "section", "article", "main"]):
            text = tag.get_text(separator="\n").strip()
            if len(text) > 500:
                # Filter out navigation and other non-content blocks
                if not any(nav_word in text.lower()[:200] for nav_word in
                           ['navigation', 'menu', 'footer', 'header', 'cookie', 'privacy', 'terms']):
                    blocks.append((len(text), text))
        if blocks:
            blocks.sort(reverse=True)
            best_content = blocks[0][1]
            logger.info(f"✅ BS4 largest meaningful block ({len(best_content)} chars)")
            return best_content
        # Readability fallback
        try:
            doc = Document(html)
            summary = BeautifulSoup(doc.summary(), "html.parser").get_text(separator="\n").strip()
            logger.debug(f"[Readability] length={len(summary) if summary else 0}")
            if len(summary) > 200:
                logger.info(f"✅ Readability ({len(summary)} chars)")
                return summary
        except Exception as e:
            logger.debug(f"[Readability error] {e}", exc_info=True)
        # Final fallback to paragraphs
        ps = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 50]
        if ps:
            txt = "\n\n".join(ps)
            logger.info(f"✅ BS4 paragraphs fallback ({len(txt)} chars)")
            return txt
        logger.debug(f"[Fallbacks] No content extracted at any step!")
        return None

    async def scrape_url(self, url: str, content_type: str = None) -> Optional[str]:
        """
        Orchestrate robust, ethical scraping, applying speed/stealth/fallbacks:
          1) SEC filings: Use sec-api (for EDGAR HTML, now with .txt fallback).
          2) News: 
              a. Resolve link (handle aggregator redirects)
              b. Check robots.txt
              c. Try trafilatura, then newspaper3k, then bs4 (sync)
              d. If all fail, run stealth Playwright and extract main content
        Returns text or None.
        Accepts optional content_type for API compatibility.
        """
        if not url:
            return None

        # SEC filings: use sec-api instead of standard scraping (now with .txt fallback)
        if content_type in ("sec_filing", "sec") or (
            "sec.gov/Archives/edgar/" in url and url.endswith(".htm")
        ):
            content = await asyncio.to_thread(self._get_secapi_filing_content, url)
            if content:
                return content
            logger.warning(f"[SECAPI] Fallback to generic scraping for: {url}")
            # ... do not return, keep going if SECAPI/.txt fails ...

        # 1) Follow aggregator redirects
        try:
            url = self._resolve_redirects(url)
        except Exception as e:
            logger.warning(f"Redirect error: {e}")

        # 2) robots.txt (skip for MSN aggregator issues)
        if 'msn.com' not in url:
            try:
                allowed = await asyncio.to_thread(can_fetch, url, random.choice(self.user_agents))
                if not allowed:
                    logger.warning(f"❌ robots.txt disallows: {url}")
                    return None
            except Exception as e:
                logger.debug(f"robots.txt check failed: {e}")

        # 3) For MSN, skip straight to Playwright for better success rate
        if 'msn.com' in url:
            logger.info(f"[MSN] Skipping sync methods, going straight to Playwright for: {url}")
            try:
                html = await self._get_page_with_stealth(url)
                content = self._extract_content_with_fallbacks(html)
                if content:
                    return content
            except Exception as e:
                logger.error(f"Playwright pipeline failed for MSN: {e}")
        else:
            # 3) Lightweight extraction pipeline for non-MSN sites
            for method in (self._method_trafilatura, self._method_newspaper, self._method_bs4):
                try:
                    content = await asyncio.to_thread(method, url)
                    if content and len(content) > 200:
                        return content
                except Exception as e:
                    logger.debug(f"{method.__name__} raised {e}")
            # 4) Playwright+stealth fallback
            try:
                html = await self._get_page_with_stealth(url)
                content = self._extract_content_with_fallbacks(html)
                if content:
                    return content
            except Exception as e:
                logger.error(f"Playwright pipeline failed: {e}")
        logger.error(f"❌ All methods failed for {url}")
        return None

    async def scrape_multiple_urls(self, urls: List[str]) -> Dict[str, str]:
        results: Dict[str, str] = {}
        for u in urls:
            logger.info(f"🔄 Scraping {u}")
            txt = await self.scrape_url(u)
            if txt:
                results[u] = txt
            sleep_time = random.uniform(2, 4) if 'msn.com' in u else random.uniform(1, 3)
            await asyncio.sleep(sleep_time)
        return results

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        if self.session:
            self.session.close()