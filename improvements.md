# ET Money Mentor - Proposed Improvements

Based on the product requirements (Image) and the synthesized academic research, the following improvements must be made to align the codebase with the complete vision.

## 1. Couple's Money Planner (Joint Financial Planning)
**Status:** Missing entirely from `src/main.py` and `dashboard/app.py` (which currently only use `IndividualProfile`).
**Image Requirement:** India's first AI-powered joint financial planning tool. Both partners input data to optimize HRA, NPS, SIP splits for tax efficiency, and joint vs individual insurance.
**Research Backing (Paper 4):** The ICAI Joint Taxation Proposal for married couples suggests that the app should model optional joint taxation scenarios (e.g., doubling the basic exemption limit to Rs 6 lakh) to future-proof the platform.
**Implementation Steps:**
- Create a `CoupleProfile` data model containing two `IndividualProfile`s.
- Add joint optimization logic for HRA claims across two incomes.
- Add "What-If" modeling for the ICAI joint taxation proposal.

## 2. Mutual Fund (MF) Portfolio X-Ray via CAS Upload
**Status:** The current system allows manual SIP entry but lacks automated portfolio reconstruction, XIRR analysis, and overlap detection.
**Image Requirement:** Upload CAMS/KFintech statements; parse in 10s for portfolio reconstruction, true XIRR, overlap analysis, and expense ratio drag.
**Research Backing (Paper 2 & 5):** 
- **Tools:** Integrate `casparser` to extract mutual fund data and `mftool` for historical NAVs (Paper 5).
- **Behavioral Detection:** Leverage Paper 2 findings to detect cognitive biases in the uploaded transaction history, such as *Loss Aversion* (stopping SIPs during market corrections) or *Herd Mentality* (chasing recent thematic out-performers).
**Implementation Steps:**
- Add `casparser` endpoints for PDF upload.
- Implement XIRR calculation and overlap analysis on the extracted ISINs.
- Add an AI diagnostic layer that flags behavioral biases based on transaction timing.

## 3. Tax Wizard: Form-16 Automation
**Status:** Tax Wizard is currently a manual entry form.
**Image Requirement:** "Upload Form 16 or input salary structure."
**Research Backing (Paper 5):**
- **Tools:** Integrate `pdfplumber` or `Camelot` to parse structured Form-16 PDFs into the Pydantic `SalaryInput` and `DeductionInput` schemas.
**Implementation Steps:**
- Build a document parsing pipeline for Form-16/salary slips.
- Map extracted PDF tables to existing tax calculator engines.

## 4. Advanced Conversational AI Integration (Fin-Ally)
**Status:** `MoneyMentorSupervisor` is a standard agent.
**Research Backing (Paper 1, 3 & 5):**
- **Fin-Ally Commonsense:** Embed the conversational AI with a Commonsense Reasoning framework (like COMET-BART) to prevent unprofessional financial advice (Paper 1).
- **DPO Alignment:** The agent should be structured to utilize DPO-aligned models, particularly trained on the *Fin-Vault* dataset.
- **Orchestration:** Transition from a basic script to `LangGraph` or `CrewAI` (Paper 5) to handle complex, multi-step sequential financial workflows (e.g., passing context from Tax Wizard to Goal Planner natively).
**Implementation Steps:**
- Refactor `src/agents/supervisor.py` to utilize LangGraph/CrewAI.
- Inject behavioral guardrails (politeness, objective reasoning) into the system prompts to mirror Fin-Ally's findings on trustworthy advice.
