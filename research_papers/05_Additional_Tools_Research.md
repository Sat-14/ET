# Additional Tools & Frameworks Research for ET Money Mentor

## 1. CAS Parsers (Mutual Fund Statement Parsing)

### casparser (codereverser/casparser) - PRIMARY RECOMMENDATION
- **GitHub:** https://github.com/codereverser/casparser
- **License:** MIT (default), GNU GPL v3 with mupdf
- **Features:** Parse CAMS/KFintech CAS PDFs, ISIN/AMFI code identification, CLI tool
- **Language:** Python
- **Status:** Well-maintained, widely used

### CASParser API (casparser.in)
- **URL:** https://casparser.in/
- **Features:** REST API for CDSL, NSDL, CAMS, KFintech - all 9 asset classes
- **Note:** After SEBI shut down MFcentral (Sep 2025), many fintechs switched to this
- **SDKs:** Python, Node.js, TypeScript

### cas-parser-python (CASParser/cas-parser-python)
- **GitHub:** https://github.com/CASParser/cas-parser-python
- **Features:** Official Python SDK for CASParser API

---

## 2. XIRR & MF Return Calculation

### mftool
- **GitHub:** https://github.com/NayakwadiS/mftool
- **PyPI:** https://pypi.org/project/mftool/
- **Features:** Historical NAV data, scheme information, daily updates for all Indian MFs
- **No external dependencies** - all part of standard Python

### MFAPI.in
- **URL:** https://api.mfapi.in
- **Features:** Free REST API, historical NAV, no auth required
- **Coverage:** All Indian mutual funds

---

## 3. Indian Income Tax Calculators

### choose-tax-regime (25b3nk)
- **GitHub:** https://github.com/25b3nk/choose-tax-regime
- **Features:** Compare old vs new regime, Python script

### TaxCalc (subhashhhhhh)
- **GitHub:** https://github.com/subhashhhhhh/TaxCalc
- **Features:** 2025 Budget slabs, Section 80C/80D/HRA/LTA/NPS deductions

### tax_calculator_by_yousaf
- **GitHub:** https://github.com/yousafkhamza/tax_calculator_by_yousaf
- **Features:** FY 2025-26 slabs, monthly/yearly inputs

---

## 4. AI/LLM Frameworks

### LangGraph (RECOMMENDED for agent orchestration)
- **URL:** https://www.langchain.com/langgraph
- **License:** MIT
- **Why:** Graph-based stateful multi-agent orchestration, used by JP Morgan, BlackRock
- **90M+ monthly downloads**

### CrewAI (RECOMMENDED for role-based agents)
- **URL:** https://crewai.com/
- **Why:** Role-based agent model (researcher, analyst, advisor), 15-20% fewer tokens
- **Best for:** Sequential financial workflows like tax analysis

### FinGPT (RECOMMENDED for financial sentiment)
- **GitHub:** https://github.com/AI4Finance-Foundation/FinGPT
- **Features:** Open-source financial LLM, LoRA fine-tuning, sentiment analysis
- **Cost:** <$300 per fine-tuning

---

## 5. Vernacular / Multilingual NLP

### AI4Bharat / IndicNLP
- **GitHub:** https://github.com/AI4Bharat/indicnlp_catalog
- **Models:** IndicBERT (12 Indian languages), IndicBART (11 languages)
- **Coverage:** Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati + more

### Approach for Money Mentor
- Use Claude/GPT-4 with Hindi/Hinglish prompts (zero-shot multilingual)
- IndicBERT for language detection and routing
- Few-shot examples from ET Money, ClearTax Hindi content

---

## 6. WhatsApp Bot Frameworks

### Baileys (WhiskeySockets/Baileys)
- Lightweight WhatsApp Web API (Node.js)
- No official API needed, works with multi-device

### WhatsApp Business API (Official)
- Meta's official API via Cloud API
- Free tier: 1,000 conversations/month
- Best for production deployment

### python-whatsapp-bot (daveebbelaar)
- **GitHub:** https://github.com/daveebbelaar/python-whatsapp-bot
- Pure Python, integrates with OpenAI/Claude

---

## 7. FIRE / Retirement Calculators

### Findia
- **URL:** https://findiafindiafindia.github.io/
- **Features:** India-specific FIRE calculator, Monte Carlo + historical Nifty data

### WenFire
- **GitHub:** https://github.com/basnijholt/wenfire
- **Features:** FastAPI + Bootstrap, financial independence visualization

---

## 8. PDF Parsing (Form-16, Salary Slips)

### pdfplumber (Python)
- Best for structured PDFs like Form-16
- Table extraction, text extraction with coordinates

### Camelot (Python)
- Specialized in table extraction from PDFs
- Works well with Indian government forms

### PyMuPDF (fitz)
- Fast PDF parsing, used by casparser internally

---

## 9. Frontend / Dashboard

### Streamlit (RECOMMENDED for hackathon MVP)
- **URL:** https://streamlit.io/
- Rapid prototyping, Python-native, built-in charting
- Many Indian finance dashboard examples exist

### Plotly Dash
- More customizable than Streamlit
- Better for complex financial dashboards
