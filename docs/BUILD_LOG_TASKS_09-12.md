# Agentic Account Research System - Build Log (Tasks 9-12)

---

## Begin Task 9: Develop & Test Triage & Categorization Function

**Description:**
Create the triage function to categorize and prioritize incoming data.

**Commands:**
```bash
mkdir -p sk_functions/Triage
```

**File:** `sk_functions/Triage/skprompt.txt`
```
You are a triage analyst. Your job is to classify a piece of text and determine its relevance.
Respond ONLY with a JSON object.

Possible categories: "SEC Filing", "News Article", "Procurement Notice", "Irrelevant".
A text is relevant if it discusses specific financial events, partnerships, or procurement needs for one of the target companies.
A text is irrelevant if it's a generic market report or only mentions a target company in a list.

Target companies to monitor:
- Capital One
- Truist
- Freddie Mac
- Navy Federal
- PenFed
- Fannie Mae
- EagleBank
- Capital Bank N.A.

Input Text:
        {{$input}}
        
JSON Output:
{
  "category": "...",
  "is_relevant": true/false,
  "reasoning": "A brief explanation for your decision."
} 
```

End Task 9

---

## Begin Task 10: Develop & Test Financial event Specialist Function

**Description:**
Create the financial specialist function to analyze financial events and data.

**Commands:**
```bash
mkdir -p sk_functions/FinancialSpecialist
```

**File:** `sk_functions/FinancialSpecialist/skprompt.txt`
```
You are a financial event detection specialist. Analyze the text to find mentions of new funding rounds, mergers, acquisitions, or partnerships.
Only identify events with a stated value greater than $10 million USD.
If no such event is found, respond with `{"event_found": false}`.
If an event is found, provide the details in a JSON object.

Target companies to monitor:
- Capital One
- Truist
- Freddie Mac
- Navy Federal
- PenFed
- Fannie Mae
- EagleBank
- Capital Bank N.A.

Input Text:
        {{$input}}
        
JSON Output:
{
  "event_found": true/false,
  "event_type": "M&A" | "Funding" | "Partnership" | "Investment",
  "value_usd": (integer),
  "summary": "A one-sentence summary of the event.",
  "company": "Company name involved"
} 
```

End Task 10

---

## Begin Task 11: Develop & Test Procurement & Earnings Call Specialist Function

**Description:**
Create the procurement and earnings call specialist function to analyze procurement notices and earnings call transcripts.

**Commands:**
```bash
mkdir -p sk_functions/ProcurementSpecialist
mkdir -p sk_functions/EarningsCallSpecialist
```

**File:** `sk_functions/ProcurementSpecialist/skprompt.txt`
```
You are a procurement specialist. Analyze the procurement notice to confirm it is an active RFP or SOW with a potential value over $10 million USD. 

Extract the core details, and specifically look for and extract any monetary values mentioned. Only flag the notice as relevant if the value is $10 million or greater. If the criteria are not met, respond with {"is_relevant": false}.

Target companies to monitor:
- Capital One
- Truist
- Freddie Mac
- Navy Federal
- PenFed
- Fannie Mae
- EagleBank
- Capital Bank N.A.

Input Text:
        {{$input}}
        
JSON Output:
{
  "is_relevant": true/false,
  "title": "...",
  "value_usd": (integer),
  "summary": "A brief summary of the work required.",
  "deadline": "Response deadline if mentioned",
  "company": "Company name if mentioned"
} 
```

**File:** `sk_functions/EarningsCallSpecialist/skprompt.txt`
```
You are an earnings call analyst. Analyze the earnings call transcript to find forward-looking statements about new or notable spending, investments, or strategic initiatives over $10 million USD.

Focus on capital allocation, technology investments, partnerships, or expansion plans. Specifically extract and validate any monetary values mentioned, and only flag as relevant if the value is $10 million or greater. If no such guidance is found, respond with {"guidance_found": false}.

Target companies to monitor:
- Capital One
- Truist
- Freddie Mac
- Navy Federal
- PenFed
- Fannie Mae
- EagleBank
- Capital Bank N.A.

Input Text:
{{$input}}

JSON Output:
{
  "guidance_found": true/false,
  "spending_type": "Technology" | "Expansion" | "Partnership" | "Investment" | "Acquisition",
  "value_usd": (integer),
  "summary": "A brief summary of the forward-looking spending guidance.",
  "timeframe": "When this spending is expected to occur",
  "company": "Company name"
} 
```

End Task 11

---

## Begin Task 12: Develop & Test Insight Generator Function

**Description:**
Create the insight generator function to generate structured insights from events.

**Commands:**
```bash
mkdir -p sk_functions/InsightGenerator
```

**File:** `sk_functions/InsightGenerator/skprompt.txt`
```
You are a strategy consultant. You have been given structured data about a significant corporate event.
Generate a concise, three-bullet brief in a JSON format.

Input Data (JSON):
        {{$input}}
        
JSON Output:
{
  "what_happened": "A concise, neutral summary of the event.",
  "why_it_matters": "The immediate impact on the company, its market, or its strategy.",
  "consulting_angle": "The potential opportunity or risk this creates that would be relevant to a consultant (e.g., need for integration planning, new technology adoption, market entry strategy)."
} 
```

End Task 12

---

## Note: Semantic Kernel Function Architecture

**Update:**
All Semantic Kernel functions are now implemented as prompt files (skprompt.txt) rather than Python classes. This approach:
- Simplifies the codebase
- Makes functions easier to maintain and update
- Ensures consistency across all AI functions
- Reduces code complexity and potential bugs

The AnalystAgent loads these prompt files directly using `kernel.add_function()` with the `prompt_template_file` parameter. 