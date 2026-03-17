"""Language detection and Hindi/Hinglish support utilities.

Provides:
- Language detection (English, Hindi, Hinglish)
- Financial term glossary (English <-> Hindi)
- Response formatting for vernacular output
"""

from __future__ import annotations

import re

# Hindi Unicode range
HINDI_PATTERN = re.compile(r"[\u0900-\u097F]")
# Common Hinglish words
HINGLISH_MARKERS = {
    "kaise", "kya", "hai", "hain", "mera", "meri", "kitna", "kitni",
    "kab", "kaha", "kaun", "kyun", "aur", "ya", "nahi", "nahin",
    "accha", "theek", "paise", "paisa", "bachat", "nivesh",
    "bhai", "yaar", "matlab", "samajh", "batao", "bata",
    "chahiye", "karke", "karo", "karna", "dena", "lena",
    "bohot", "bahut", "thoda", "zyada", "kam", "jyada",
    "salary", "tax", "sip", "fund", "loan", "emi",
}


class Language:
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hi-en"


def detect_language(text: str) -> str:
    """Detect if text is English, Hindi, or Hinglish."""
    if not text:
        return Language.ENGLISH

    # Check for Devanagari script
    hindi_chars = len(HINDI_PATTERN.findall(text))
    total_alpha = sum(1 for c in text if c.isalpha())

    if total_alpha == 0:
        return Language.ENGLISH

    hindi_ratio = hindi_chars / total_alpha

    if hindi_ratio > 0.5:
        return Language.HINDI
    elif hindi_ratio > 0.1:
        return Language.HINGLISH

    # Check for Hinglish (Roman script Hindi words)
    words = text.lower().split()
    hinglish_count = sum(1 for w in words if w in HINGLISH_MARKERS)
    if len(words) > 0 and (hinglish_count / len(words)) > 0.2:
        return Language.HINGLISH

    return Language.ENGLISH


# Financial glossary: English -> Hindi
FINANCIAL_GLOSSARY = {
    "mutual fund": "म्यूचुअल फंड",
    "sip": "SIP (सिस्टमैटिक इन्वेस्टमेंट प्लान)",
    "tax": "कर / टैक्स",
    "tax saving": "टैक्स बचत",
    "income tax": "आयकर",
    "deduction": "कटौती",
    "investment": "निवेश",
    "return": "रिटर्न",
    "profit": "लाभ / मुनाफा",
    "loss": "नुकसान / हानि",
    "portfolio": "पोर्टफोलियो",
    "emergency fund": "आपातकालीन कोष",
    "insurance": "बीमा",
    "life insurance": "जीवन बीमा",
    "health insurance": "स्वास्थ्य बीमा",
    "retirement": "सेवानिवृत्ति / रिटायरमेंट",
    "pension": "पेंशन",
    "savings": "बचत",
    "expense": "खर्च",
    "income": "आय / इनकम",
    "salary": "वेतन / सैलरी",
    "loan": "ऋण / लोन",
    "emi": "EMI (मासिक किस्त)",
    "interest": "ब्याज",
    "compound interest": "चक्रवृद्धि ब्याज",
    "inflation": "मुद्रास्फीति / महंगाई",
    "budget": "बजट",
    "goal": "लक्ष्य",
    "debt": "कर्ज",
    "equity": "इक्विटी",
    "large cap": "लार्ज कैप",
    "mid cap": "मिड कैप",
    "small cap": "स्मॉल कैप",
    "nav": "NAV (नेट एसेट वैल्यू)",
    "xirr": "XIRR (एक्सटेंडेड इंटरनल रेट ऑफ रिटर्न)",
    "ppf": "PPF (पब्लिक प्रोविडेंट फंड)",
    "epf": "EPF (कर्मचारी भविष्य निधि)",
    "nps": "NPS (नेशनल पेंशन सिस्टम)",
    "elss": "ELSS (इक्विटी लिंक्ड सेविंग स्कीम)",
    "hra": "HRA (हाउस रेंट अलाउंस)",
    "financial independence": "वित्तीय स्वतंत्रता",
}


def get_hindi_term(english_term: str) -> str:
    """Get Hindi equivalent of a financial term."""
    return FINANCIAL_GLOSSARY.get(english_term.lower(), english_term)


def get_language_instruction(language: str) -> str:
    """Get instruction for LLM to respond in the detected language."""
    if language == Language.HINDI:
        return (
            "Respond in Hindi (Devanagari script). Use Hindi financial terms "
            "where available, but keep technical terms like SIP, XIRR, NAV in English. "
            "Keep the response conversational and easy to understand."
        )
    elif language == Language.HINGLISH:
        return (
            "Respond in Hinglish (mix of Hindi and English using Roman script). "
            "Example style: 'Aapka tax old regime mein Rs 1.2L hai, lekin new regime mein sirf Rs 80K. "
            "Matlab Rs 40,000 ki saving ho sakti hai!' "
            "Keep financial terms in English but use Hindi connectors and casual tone."
        )
    else:
        return "Respond in clear, simple English."


def format_indian_number(amount: float) -> str:
    """Format number in Indian style (lakhs, crores).

    Examples:
        1500 -> "1,500"
        150000 -> "1.5 lakh"
        15000000 -> "1.5 crore"
    """
    if amount < 0:
        return "-" + format_indian_number(abs(amount))

    if amount >= 10_000_000:  # 1 crore+
        value = amount / 10_000_000
        if value == int(value):
            return f"Rs {int(value)} crore"
        return f"Rs {value:.1f} crore"
    elif amount >= 100_000:  # 1 lakh+
        value = amount / 100_000
        if value == int(value):
            return f"Rs {int(value)} lakh"
        return f"Rs {value:.1f} lakh"
    elif amount >= 1000:
        # Indian comma formatting: 1,00,000
        s = str(int(amount))
        if len(s) <= 3:
            return f"Rs {s}"
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        parts.reverse()
        return f"Rs {','.join(parts)},{last3}"
    else:
        return f"Rs {int(amount)}"
