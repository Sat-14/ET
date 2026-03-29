# ET Money Mentor

## Problem

95% of Indians don't have a financial plan. Financial advisors charge Rs 25,000+/year and serve only HNIs, leaving the vast majority without guidance.

## Solution

An AI-powered personal finance mentor that combines deterministic financial engines with conversational AI — every number comes from code, not the LLM — to deliver accurate, India-specific financial planning through chat, dashboard, and WhatsApp.

---

## What We Built

### 1. Money Health Score
Financial wellness score across 6 dimensions — emergency preparedness, insurance coverage, investment diversification, debt health, tax efficiency, and retirement readiness. Generates a downloadable PDF report with prioritized action items.

### 2. Tax Wizard
Upload Form-16 or enter salary details. Compares Old vs New regime with your exact numbers, finds every missed deduction (80C, 80D, 80CCD, HRA, 24b), and ranks tax-saving investments by risk profile and liquidity needs.

### 3. Couple's Money Planner
Both partners input their data. The system optimizes deduction allocation across both incomes, compares regime choices per partner, and produces a combined household tax strategy with optimization notes.

### 4. MF Portfolio X-Ray
Upload your CAMS/KFintech CAS statement. Get true XIRR, fund overlap detection, expense ratio drag, benchmark comparison, 5 research-backed behavioral bias patterns, and a rebalancing plan.

### 5. FIRE Path Planner
Builds a year-by-year financial roadmap — SIP amounts per goal, asset allocation shifts, insurance gaps, emergency fund targets, and tax-saving moves. Includes Monte Carlo simulation for confidence scoring.

### 6. Life Event Financial Advisor
Handles bonus, inheritance, marriage, new baby, job loss, home purchase, and more. Simulates month-by-month cashflow impact with event-specific action plans.

### AI Chat + WhatsApp
Multi-agent conversational layer supporting English, Hindi, and Hinglish. 14 tools wired to deterministic engines ensure the AI never hallucinates financial numbers.

---

## Architecture

```
User (Dashboard / API / WhatsApp)
        |
   AI Supervisor (intent routing)
        |
   Specialized Agent (tax / goals / portfolio / ...)
        |
   Deterministic Engine  <-- Numbers from code, NOT from LLM
        |
   Output (JSON / PDF / chat)
```

All financial calculations (tax, XIRR, goals, insurance, SWP, EMI) run in 15 deterministic Python engines. The LLM only explains results and handles conversation.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI |
| Dashboard | Streamlit + Plotly |
| LLM | Gemini / Groq / DeepSeek / Claude (any one) |
| Financial Engines | pyxirr (Rust-based), numpy-financial |
| Document Parsing | casparser (CAS PDFs), pdfplumber (Form-16) |
| Market Data | mftool (MF NAV), yfinance (stocks) |
| Portfolio Analytics | quantstats, PyPortfolioOpt |

---

## Research Papers

| Paper | What We Used It For |
|-------|-------------------|
| Fin-Ally (ArXiv 2509.24342) | DPO alignment approach for professional financial chatbot tone |
| Chadha 2024 — Cognitive Biases in Indian MF Investors | 5 behavioral bias detection patterns in Portfolio X-Ray |
| Nature 2025 — Conversational AI in Personal Finance | Conversational design and guardrail strategy |
| ICAI Joint Taxation Proposal | Future-proofing Couple Planner for India's proposed joint filing regime |
