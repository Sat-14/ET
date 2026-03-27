# Fixes Required for ET Money Mentor

Based on the current project state and recent developer logs, the following critical bugs and structural issues need to be resolved:

## 1. PDF Generation Errors (`fpdf2`)
- **Issue:** The `Report Generator` (`src/engines/report_generator.py`) is throwing `FPDFException` and Streamlit API exceptions during the generation and downloading of the Money Health Score and Tax Comparison PDFs.
- **Root Cause:** Likely related to incorrect cursor positioning (`get_x()`, `get_y()`, `multi_cell(...)`) or library compatibility issues with the latest `fpdf2` version. Also, data marshalling for Streamlit file downloads is failing.
- **Fix Required:** 
  - Fix `fpdf2` multi_cell cursor state bugs.
  - Fix Streamlit download button data encoding (`StreamlitAPIException`).

## 2. Missing Core Form Inputs / Parsing
- **Issue:** The `dashboard/app.py` has manual inputs for all salary components, which creates high user friction.
- **Fix Required:** Add upload logic (with parsing tools) to avoid making the user manually type every deduction.

## 3. Empty or Mocked Agent Engine Connections
- **Issue:** The `MoneyMentorSupervisor` can fail to connect to the LLM backend if keys are missing, resulting in silent failures or generic error messages shown in Streamlit.
- **Fix Required:** Add robust error handling, retries, and explicit fallback responses if the LLM backend is down or rate-limited.
