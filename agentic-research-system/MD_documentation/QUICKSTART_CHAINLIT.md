# 🚀 Quick Start Guide - Company Intelligence System

## ⚡ Get Started in 5 Minutes

### What You Need
- A computer with internet access
- Python installed (we'll help you check this)
- API keys (we'll guide you through getting these)

### Step 1: Check Your Setup

**Check if Python is installed:**
```bash
python --version
```
If you see something like "Python 3.11.x", you're good! If not, download Python from python.org.

### Step 2: Download and Setup

```bash
# Download the system
git clone <repository-url>
cd agentic-research-system

# Install the system
pip install -r requirements.txt
```

### Step 3: Install Web Browser Tools

```bash
# This helps the system read websites
playwright install --with-deps
```

### Step 4: Set Up Your API Keys

1. **Copy the template file:**
```bash
cp env.example .env
```

2. **Open the .env file** in any text editor (like Notepad, TextEdit, or VS Code)

3. **Add your API keys** - You'll need to get these from:
   - **OpenAI**: Get from https://platform.openai.com/api-keys
   - **SEC API**: Get from https://sec-api.io/
   - **GNews**: Get from https://gnews.io/
   - **Azure AI Foundry**: Your IT team can help with this

**Example of what to add:**
```
OPENAI_API_KEY=sk-your-key-here
SEC_API_KEY=your-sec-key-here
GNEWS_API_KEY=your-gnews-key-here
```

### Step 5: Launch the System


**Easy way (recommended):**
```bash
#From the root directory, type:
chainlit run chainlit_app/main.py
```


### Step 6: Use the System

1. **Open your web browser**
2. **Go to:** http://localhost:8000
3. **Type a company name** like "Capital One" or "Fannie Mae" or click the button for the respective company!
4. **Wait for the results** - it takes about 3-4 minutes to extract data from 7 sources, validate, web-scrape for full context, and then analyze.

### What the System Does

When you ask about a company, it:
- ✅ Searches recent news articles
- ✅ Checks SEC filings for important updates
- ✅ Looks for government contracts and opportunities
- ✅ Analyzes industry trends
- ✅ Uses ProConnect data to bring contact methods, current projects, and factors into analysis for consulting opportunities!
- ✅ Creates a comprehensive briefing report

### Example Results

Try asking about:
- "Capital One"
- "Navy Federal Credit Union"
- "Eagle Bank"

You'll get a report with:
- Company overview
- Recent important events
- Industry context
- Consulting opportunities
- Source links

## 🚨 If Something Goes Wrong

### Common Issues

**"Python not found"**
- Download Python from python.org
- Make sure to check "Add Python to PATH" during installation

**"API key errors"**
- Double-check your .env file has the correct keys
- Make sure there are no extra spaces or quotes

**"Port 8000 already in use"**
- Try a different port: `chainlit run main.py --port 8001`
- Then go to http://localhost:8001

**"Playwright errors"**
- Run this command: `playwright install --with-deps`

**IF NOTHING ELSE WORKS:**
- Resort to the pre-recorded demo! 

## 🎯 What's Next?

Once the system is running:
1. **Try different companies** to see how it works
2. **Share the results** with your team

## Future Iterations:
- This agentic workflow is only a subset of the proposed 'Client Visit Agent Team'
  Other Agents which are planned for integration to complete this team are : Budget vs. Actuals Agent(Analyzing budgets for insights), Status Report Agent(Drafts reports from iManage and M365 updates), and Client Touchpoint Agent(Suggests talking points, analyzes transcripts, logs events).
- The system has been developed to be easily iterated upon. This is a great base for us to add any features which you believe will be valuable - whether that's data sources or analysis! One impactful data source could be a catalog of what products/services we offer to be used for analysis and integration.
- Bear in mind, this is only a small taste of the capabilities of GenAI. For this POC, we have only aggregated data from ProConnect - the more internal data we aggregate, the more customized and valuable the results will be! Your feedback will directly shape the future of this project!



---

**🎉 You're ready to start gathering intelligence!**

The system will automatically find and analyze the latest information about any company you ask about. 


**Over-Arching Goal For the Client Visit Agent Team:**
- The goal is to automate all data collection and 85% of the analysis, leaving MD's with more time to focus on client interaction! 
- Aggregating all internal data sources to this Agent Team will provide all valuable information without having to check 8-10 different data sources, saving several hours of tedious data collection per use!
