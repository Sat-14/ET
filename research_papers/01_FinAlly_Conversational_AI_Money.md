# Fin-Ally: Pioneering the Development of an Advanced, Commonsense-Embedded Conversational AI for Money Matters

## Paper Link
- **ArXiv:** https://arxiv.org/abs/2509.24342
- **PDF:** https://arxiv.org/pdf/2509.24342

## Authors
Sarmistha Das, Priya Mathur, Ishani Sharma, Sriparna Saha (IIT Patna), Kitsuchart Pasupa, Alka Maurya

## Abstract
The research addresses a critical gap in FinTech advisory systems. While chatbots have improved user engagement, fine-tuned large language models sometimes generate contextually inappropriate responses that undermine trust. The authors note that "large-scale fine-tuning of LLMs can occasionally yield unprofessional or flippant remarks."

## Key Contributions

### 1. Fin-Vault Dataset
- A multi-turn financial conversational corpus containing **1,417 annotated dialogues**
- Extends beyond basic account management to encompass **budgeting, expense tracking, and financial planning**
- Covers: banking, credit/debit card management, insurance, and market investments

### 2. Fin-Ally Model
- An integrated system incorporating:
  - **Commonsense reasoning** via COMET-BART embedding
  - **Politeness standards**
  - **Natural conversational patterns**
  - **Direct Preference Optimization (DPO)** for human-aligned responses

## Methodology
- Leverages COMET-BART-embedded commonsense context
- Applies DPO mechanisms to align responses with human preferences
- Comprehensive empirical evaluations under both zero-shot and fine-tuned settings
- Benchmarks multiple state-of-the-art LLMs for financial chatbot deployment

## Key Finding
"Incorporating commonsense context enables language models to generate more refined, textually precise, and professionally grounded financial guidance."

## Relevance to ET Money Mentor
- **Directly applicable** to the conversational AI layer of all 6 features
- The Fin-Vault dataset can be used for training/fine-tuning the mentor chatbot
- DPO approach ensures professional, trustworthy financial advice
- Commonsense reasoning prevents inappropriate responses in sensitive financial contexts
