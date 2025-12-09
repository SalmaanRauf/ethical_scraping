"""
Protiviti Account Research Demo - Chainlit Application
This is a simulated demo for video presentation purposes.
"""

import chainlit as cl
import asyncio

# ═══════════════════════════════════════════════════════════════════════════════
# DEMO CONFIGURATION - Edit these to customize the demo
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_COMPANY = None  # Will be set from user input

# Simulated findings
WEB_RESEARCH_FINDINGS = {
    "news_articles": 5,
    "sec_filings": 2,
    "procurement_notices": 1
}

CREDENTIALS_FINDINGS = {
    "similar_projects": 3,
    "projects": [
        "Enterprise Risk Assessment for Fortune 500 Financial Services Client",
        "Digital Transformation Roadmap for Regional Banking Institution",
        "Regulatory Compliance Program for Multinational Insurance Provider"
    ]
}

TECH_ENABLER_FINDINGS = {
    "solutions": 2,
    "solution_names": [
        "Automated Regulatory Change Management Platform",
        "AI-Powered Contract Intelligence System"
    ]
}

# ═══════════════════════════════════════════════════════════════════════════════
# STYLING
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_COLORS = {
    "system": "#6366f1",      # Indigo
    "web_research": "#10b981", # Emerald
    "credentials": "#f59e0b",  # Amber
    "tech_enabler": "#8b5cf6", # Violet
    "analysis": "#ec4899",     # Pink
    "complete": "#22c55e"      # Green
}

# ═══════════════════════════════════════════════════════════════════════════════
# DEMO REPORT CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_demo_report(company: str) -> str:
    """Generate a demo report for the given company."""
    return f"""
# 📊 Account Intelligence Report: {company}

---

## Executive Summary

Based on comprehensive multi-agent research, **{company}** presents significant consulting opportunities across risk advisory, technology transformation, and regulatory compliance domains. Our analysis identified multiple engagement vectors aligned with Protiviti's core service offerings.

---

## 🔍 Web Research Findings

### Recent News & Developments
| Source | Headline | Relevance |
|--------|----------|-----------|
| Reuters | {company} Announces $2.1B Digital Transformation Initiative | ⭐⭐⭐⭐⭐ |
| WSJ | Regulatory Scrutiny Increases for {company} Operations | ⭐⭐⭐⭐ |
| Bloomberg | {company} Q3 Earnings Beat Expectations, Guides Higher | ⭐⭐⭐⭐ |
| Financial Times | {company} Expands Cloud Infrastructure Partnership | ⭐⭐⭐⭐ |
| Industry Week | {company} Named Leader in ESG Initiatives | ⭐⭐⭐ |

### SEC Filings Analysis
- **10-K Annual Report (2024)**: Risk factors highlight cybersecurity, regulatory compliance, and third-party vendor management as key concerns
- **8-K Current Report**: Material definitive agreement for technology modernization program

### Government Procurement
- **SAM.gov Notice**: RFI for Enterprise Risk Management Services (Est. Value: $15-25M)

---

## 📋 Relevant Protiviti Credentials

### Similar Engagements Completed

#### 1. Enterprise Risk Assessment — Fortune 500 Financial Services
> Delivered comprehensive risk assessment framework covering operational, regulatory, and technology risks. Resulted in 40% improvement in risk identification and $12M in avoided regulatory penalties.

**Services Delivered:** Risk Advisory, Internal Audit, Regulatory Compliance

#### 2. Digital Transformation Roadmap — Regional Banking Institution  
> Designed and implemented 3-year digital transformation strategy including cloud migration, process automation, and customer experience enhancement.

**Services Delivered:** Technology Consulting, Business Performance, Change Management

#### 3. Regulatory Compliance Program — Multinational Insurance Provider
> Built end-to-end compliance program for emerging regulations including model risk management, data privacy, and operational resilience.

**Services Delivered:** Regulatory Compliance, Model Risk, Data Privacy

---

## ⚙️ Applicable Tech Enabler Solutions

### 1. Automated Regulatory Change Management Platform
> **Description:** AI-powered platform that monitors regulatory changes, assesses impact, and generates compliance action plans automatically.
> 
> **Relevance to {company}:** Given the increased regulatory scrutiny identified in news analysis, this solution directly addresses their compliance challenges.
> 
> **Implementation Timeline:** 12-16 weeks

### 2. AI-Powered Contract Intelligence System
> **Description:** NLP-based system for contract analysis, risk identification, and obligation tracking across vendor and customer agreements.
> 
> **Relevance to {company}:** Supports the third-party risk management concerns identified in SEC filings.
> 
> **Implementation Timeline:** 8-12 weeks

---

## 🎯 Recommended Engagement Strategy

### Immediate Actions (Next 30 Days)
1. **Schedule Executive Briefing** — Present findings to MD/Partner for account planning
2. **Respond to SAM.gov RFI** — Leverage credentials for ERM services opportunity
3. **Prepare Capability Presentation** — Customize Tech Enabler demos for {company} context

### Service Line Opportunities
| Service Line | Opportunity | Est. Value | Priority |
|--------------|-------------|------------|----------|
| Risk & Compliance | Enterprise Risk Assessment | $2-4M | 🔴 High |
| Technology Consulting | Digital Transformation Advisory | $3-5M | 🔴 High |
| Internal Audit | SOX & Controls Modernization | $1-2M | 🟡 Medium |
| Data & Analytics | AI/ML Governance Framework | $1-3M | 🟡 Medium |

### Key Contacts to Engage
- **CRO / Chief Risk Officer** — Risk Advisory services
- **CIO / Chief Information Officer** — Technology transformation
- **Chief Compliance Officer** — Regulatory services

---

## 📈 Confidence Metrics

| Metric | Score |
|--------|-------|
| Data Quality | 94% |
| Source Diversity | 87% |
| Credential Match | 91% |
| Overall Confidence | **92%** |

---

*Report generated by Protiviti Account Research System*  
*Multi-Agent Intelligence Platform v2.0*
"""

# ═══════════════════════════════════════════════════════════════════════════════
# CHAINLIT EVENT HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@cl.on_chat_start
async def start():
    """Initialize the chat session with welcome message."""
    
    welcome_message = """
# 🏢 Protiviti Account Research System

Welcome to the **Multi-Agent Account Intelligence Platform**.

Enter a **company name** to begin comprehensive account research.

*Example: "Capital One", "Microsoft", "Johnson & Johnson"*
"""
    
    await cl.Message(content=welcome_message).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages and run the demo simulation."""
    
    company = message.content.strip()
    
    if not company:
        await cl.Message(content="Please enter a company name to begin research.").send()
        return
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Request Received from ProConnect
    # ─────────────────────────────────────────────────────────────────────────
    
    await cl.Message(
        content=f"📥 **Account Research request on {company} received from ProConnect...**"
    ).send()
    
    await asyncio.sleep(3)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Dispatching Agents
    # ─────────────────────────────────────────────────────────────────────────
    
    await cl.Message(
        content="🚀 **Dispatching Agents to handle the request...**"
    ).send()
    
    await asyncio.sleep(2)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Agent Dispatch Notifications
    # ─────────────────────────────────────────────────────────────────────────
    
    # Web Research Agent
    await cl.Message(
        content=f"🔍 **Web Research Agent** dispatched to discover any relevant news, SEC filings, or other public data regarding **{company}**"
    ).send()
    
    await asyncio.sleep(0.8)
    
    # Credentials Agent
    await cl.Message(
        content=f"📋 **Credentials Agent** dispatched to discover similar work we've done for other clients which we can recommend to **{company}**"
    ).send()
    
    await asyncio.sleep(0.8)
    
    # Tech Enabler Agent
    await cl.Message(
        content=f"⚙️ **Tech Enabler Agent** dispatched to discover what solutions we have built or are building in other projects which are applicable to **{company}**"
    ).send()
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Simulated Research Progress (optional visual enhancement)
    # ─────────────────────────────────────────────────────────────────────────
    
    # Create a progress message that we'll update
    progress_msg = cl.Message(content="⏳ **Agents are researching...**")
    await progress_msg.send()
    
    # Simulate some research time with progress updates
    await asyncio.sleep(2)
    progress_msg.content = "⏳ **Agents are researching...** (Web Research: Scanning sources...)"
    await progress_msg.update()
    
    await asyncio.sleep(1.5)
    progress_msg.content = "⏳ **Agents are researching...** (Credentials: Matching projects...)"
    await progress_msg.update()
    
    await asyncio.sleep(1.5)
    progress_msg.content = "⏳ **Agents are researching...** (Tech Enabler: Identifying solutions...)"
    await progress_msg.update()
    
    await asyncio.sleep(1)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Research Complete - Results Summary
    # ─────────────────────────────────────────────────────────────────────────
    
    results_message = f"""
## ✅ Research Complete

---

🔍 **Web Research Agent** discovered:
- **{WEB_RESEARCH_FINDINGS['news_articles']}** relevant news articles
- **{WEB_RESEARCH_FINDINGS['sec_filings']}** SEC filings
- **{WEB_RESEARCH_FINDINGS['procurement_notices']}** procurement notice

---

📋 **Credentials Agent** retrieved the following **{CREDENTIALS_FINDINGS['similar_projects']}** relevant similar projects Protiviti has completed:
"""
    
    for i, project in enumerate(CREDENTIALS_FINDINGS['projects'], 1):
        results_message += f"\n   {i}. {project}"
    
    results_message += f"""

---

⚙️ **Tech Enabler Agent** discovered **{TECH_ENABLER_FINDINGS['solutions']}** similar solutions the Protiviti Data Science & Innovation team has built:
"""
    
    for i, solution in enumerate(TECH_ENABLER_FINDINGS['solution_names'], 1):
        results_message += f"\n   {i}. {solution}"
    
    await cl.Message(content=results_message).send()
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: Analyzing Findings
    # ─────────────────────────────────────────────────────────────────────────
    
    analyzing_msg = cl.Message(content="🧠 **Analyzing all findings...**")
    await analyzing_msg.send()
    
    # Simulate analysis with progress
    await asyncio.sleep(1.5)
    analyzing_msg.content = "🧠 **Analyzing all findings...** (Cross-referencing data sources...)"
    await analyzing_msg.update()
    
    await asyncio.sleep(1.5)
    analyzing_msg.content = "🧠 **Analyzing all findings...** (Identifying opportunity signals...)"
    await analyzing_msg.update()
    
    await asyncio.sleep(1)
    analyzing_msg.content = "🧠 **Analyzing all findings...** (Generating recommendations...)"
    await analyzing_msg.update()
    
    await asyncio.sleep(1)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 7: Analysis Complete with View Report Button
    # ─────────────────────────────────────────────────────────────────────────
    
    # Store the company name in session for the button callback
    cl.user_session.set("demo_company", company)
    
    # Create the action button
    actions = [
        cl.Action(
            name="view_report",
            label="📊 View Final Report",
            payload={"company": company}
        )
    ]
    
    await cl.Message(
        content=f"""
## ✨ Analysis Complete

All agent findings have been synthesized into a comprehensive account intelligence report for **{company}**.

Click below to view the full report:
""",
        actions=actions
    ).send()


@cl.action_callback("view_report")
async def on_view_report(action: cl.Action):
    """Handle the View Report button click."""
    
    company = action.payload.get("company", "Unknown Company")
    
    # Generate and display the full report
    report = generate_demo_report(company)
    
    await cl.Message(content=report).send()
    
    # Add a follow-up prompt
    await cl.Message(
        content="""
---

💬 **What would you like to do next?**

- Enter another company name to research
- Ask follow-up questions about this report
- Request specific details on any section
"""
    ).send()

