# Optimized SK Functions System

## **System Overview**

The optimized SK functions work together in a cohesive workflow with clear, non-overlapping responsibilities:

```
Raw Data → Triage → Specialist Analysis → Insight Generation → Validation → Archiving
```

## **Function Roles & Responsibilities**

### **1. Triage Function** (`sk_functions/Triage/optimized_skprompt.txt`)
**Purpose**: Initial classification and routing
**Input**: Raw text from any source
**Output**: Classification and routing decision
**Responsibilities**:
- Quick relevance assessment
- Category classification (SEC Filing, News Article, Procurement Notice, Earnings Call, Irrelevant)
- Confidence scoring
- Routing hints for specialist analysis

**No Overlap**: Does NOT do detailed analysis - only classification

### **2. Financial Specialist** (`sk_functions/FinancialSpecialist/optimized_skprompt.txt`)
**Purpose**: Detailed analysis of news articles and SEC filings
**Input**: Text classified as "SEC Filing" or "News Article"
**Output**: High-impact event detection
**Responsibilities**:
- Extract monetary values (≥ $10M threshold)
- Identify event types (M&A, Funding, Regulatory, Technology, etc.)
- Assess strategic significance
- Evaluate consulting opportunities
- Note regulatory implications

**No Overlap**: Only handles news and SEC filings, not procurement or earnings calls

### **3. Procurement Specialist** (`sk_functions/ProcurementSpecialist/optimized_skprompt.txt`)
**Purpose**: Analysis of procurement notices and consultant opportunities
**Input**: Text classified as "Procurement Notice"
**Output**: Consulting opportunity assessment
**Responsibilities**:
- Validate RFP/SOW relevance (≥ $10M threshold)
- Identify consulting service categories
- Extract project details and deadlines
- Assess competitive landscape
- Evaluate opportunity fit

**No Overlap**: Only handles procurement notices, not news or earnings calls

### **4. Earnings Call Specialist** (`sk_functions/EarningsCallSpecialist/optimized_skprompt.txt`)
**Purpose**: Analysis of forward-looking guidance and spending plans
**Input**: Text classified as "Earnings Call"
**Output**: Future spending guidance detection
**Responsibilities**:
- Identify forward-looking statements
- Extract spending guidance (≥ $10M threshold)
- Determine implementation timeline
- Assess strategic significance
- Evaluate consulting opportunities

**No Overlap**: Only handles earnings call transcripts, not current events or procurement

### **5. Insight Generator** (`sk_functions/InsightGenerator/optimized_skprompt.txt`)
**Purpose**: Generate structured insights from all specialist analyses
**Input**: Results from any specialist function
**Output**: Strategic insights and consulting opportunities
**Responsibilities**:
- Create structured insights (what happened, why it matters, consulting angle)
- Assess priority and timeline
- Identify specific consulting services needed
- Evaluate business impact

**No Overlap**: Works with all specialist outputs, creates final insights

## **Workflow Integration**

### **Data Flow**:
1. **Raw Data** → Triage (classification)
2. **Classified Data** → Appropriate Specialist (detailed analysis)
3. **Specialist Results** → Insight Generator (strategic insights)
4. **Final Insights** → Validation & Archiving

### **Error Handling**:
- Triage confidence scores guide validation decisions
- Specialist confidence scores affect archiving priority
- Irrelevant data is filtered out early
- Low-confidence results are flagged for review

### **Performance Optimization**:
- Triage filters out irrelevant data quickly
- Specialists focus on their domain expertise
- Insight generator creates consistent output format
- Confidence scores enable intelligent prioritization

## **Key Improvements**

### **1. Clear Separation of Concerns**
- **Triage**: Classification only
- **Specialists**: Domain-specific analysis
- **Insight Generator**: Strategic synthesis

### **2. Consistent Standards**
- All functions use same target companies list
- Consistent $10M threshold across specialists
- Standardized confidence scoring
- Uniform JSON output formats

### **3. Enhanced Capabilities**
- **Triage**: Added "Earnings Call" category and confidence scoring
- **Financial**: Added regulatory impact and risk factor analysis
- **Procurement**: Added consulting type classification
- **Earnings**: Added forward-looking guidance detection
- **Insight**: Added priority and timeline assessment

### **4. Consulting Focus**
- All functions identify consulting opportunities
- Procurement specialist focuses on RFP opportunities
- Financial specialist notes strategic consulting needs
- Earnings specialist identifies future consulting demand
- Insight generator synthesizes all opportunities

## **Usage Examples**

### **Example 1: SEC Filing**
```
Raw Data → Triage (SEC Filing, high confidence) → Financial Specialist → Insight Generator
```

### **Example 2: Procurement Notice**
```
Raw Data → Triage (Procurement Notice, high confidence) → Procurement Specialist → Insight Generator
```

### **Example 3: Earnings Call**
```
Raw Data → Triage (Earnings Call, high confidence) → Earnings Call Specialist → Insight Generator
```

### **Example 4: Irrelevant Data**
```
Raw Data → Triage (Irrelevant, low confidence) → Filtered out
```

## **Benefits**

1. **Improved Accuracy**: Specialized analysis for each data type
2. **Better Performance**: Early filtering of irrelevant data
3. **Enhanced Insights**: Consistent strategic analysis
4. **Consulting Focus**: All functions identify business opportunities
5. **Scalable**: Clear separation allows independent optimization
6. **Maintainable**: Each function has single responsibility

## **Next Steps**

1. **Test the optimized functions** with real data
2. **Update the analyst agent** to use optimized functions
3. **Validate performance** against current system
4. **Monitor accuracy** and adjust as needed 