"""Deterministic EN/KN letters: one fixed, reviewed sentence per clause type, plus the prototype templates.

The model's own wording is never put in a letter or called translated; each finding contributes
its clause reference and a sentence chosen by its category.
"""
from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any
from uuid import uuid4

from housing.messages import draft_messages

LOGGER = logging.getLogger(__name__)
SCHEDULED: dict[str, dict[str, str]] = {}
HEADERS = {
    "challenge": {"en": "Please reconsider the proposed deductions and provide an itemised explanation with supporting evidence.",
                  "kn": "ಪ್ರಸ್ತಾಪಿತ ಕಡಿತಗಳನ್ನು ದಯವಿಟ್ಟು ಮರುಪರಿಶೀಲಿಸಿ ಮತ್ತು ಪುರಾವೆಗಳೊಂದಿಗೆ ವಿವರವಾದ ಲೆಕ್ಕವನ್ನು ನೀಡಿ.",
                  "hi": "कृपया प्रस्तावित कटौतियों पर फिर से विचार करें और सबूतों के साथ मदवार विवरण दें।"},
    "notice": {"en": "I am following up on my earlier request. Please respond in writing within seven days so we can resolve the outstanding amount.",
               "kn": "ನನ್ನ ಹಿಂದಿನ ವಿನಂತಿಯನ್ನು ಮತ್ತೆ ನೆನಪಿಸುತ್ತಿದ್ದೇನೆ. ಬಾಕಿ ಮೊತ್ತವನ್ನು ಪರಿಹರಿಸಲು ದಯವಿಟ್ಟು ಏಳು ದಿನಗಳಲ್ಲಿ ಲಿಖಿತ ಉತ್ತರ ನೀಡಿ.",
               "hi": "यह मेरे पिछले अनुरोध का अनुस्मारक है। बकाया राशि का निपटारा करने के लिए कृपया सात दिनों के भीतर लिखित उत्तर दें।"},
}


# What to ask for, by finding category. "request" is used before signing; "challenge" and "notice" at move-out.
ASKS: dict[str, dict[str, dict[str, str]]] = {
    "deposit_forfeiture": {
        "request": {"en": "please replace forfeiture of the whole deposit with deduction of actual, itemised loss (Indian Contract Act, 1872, s.74).",
                    "kn": "ಸಂಪೂರ್ಣ ಠೇವಣಿ ಮುಟ್ಟುಗೋಲಿನ ಬದಲು, ನಿಜವಾದ ಮತ್ತು ವಿವರವಾದ ನಷ್ಟವನ್ನು ಮಾತ್ರ ಕಡಿತಗೊಳಿಸಿ (ಭಾರತೀಯ ಒಪ್ಪಂದ ಕಾಯ್ದೆ, 1872, ಸೆಕ್ಷನ್ 74).",
                    "hi": "कृपया पूरी जमा राशि ज़ब्त करने के बजाय केवल वास्तविक, मदवार नुकसान की कटौती करें (भारतीय संविदा अधिनियम, 1872, धारा 74)।"},
        "challenge": {"en": "please refund this deduction or show the actual, itemised loss it covers (Indian Contract Act, 1872, s.74).",
                      "kn": "ಈ ಕಡಿತವನ್ನು ಹಿಂತಿರುಗಿಸಿ, ಅಥವಾ ಇದು ಒಳಗೊಳ್ಳುವ ನಿಜವಾದ ಮತ್ತು ವಿವರವಾದ ನಷ್ಟವನ್ನು ತೋರಿಸಿ (ಭಾರತೀಯ ಒಪ್ಪಂದ ಕಾಯ್ದೆ, 1872, ಸೆಕ್ಷನ್ 74).",
                      "hi": "कृपया यह कटौती लौटाएँ, या वह वास्तविक, मदवार नुकसान दिखाएँ जिसके लिए यह की गई है (भारतीय संविदा अधिनियम, 1872, धारा 74)।"},
    },
    "lock_in": {
        "request": {"en": "please cap the early-exit payment at one month's rent, or waive it if I find a replacement tenant.",
                    "kn": "ಬೇಗ ಖಾಲಿ ಮಾಡಿದರೆ ಪಾವತಿಯನ್ನು ಒಂದು ತಿಂಗಳ ಬಾಡಿಗೆಗೆ ಮಿತಿಗೊಳಿಸಿ, ಅಥವಾ ನಾನು ಬದಲಿ ಬಾಡಿಗೆದಾರರನ್ನು ಹುಡುಕಿದರೆ ಮನ್ನಾ ಮಾಡಿ.",
                    "hi": "कृपया समय से पहले घर छोड़ने पर भुगतान को एक महीने के किराए तक सीमित करें, या दूसरा किरायेदार मिलने पर इसे माफ़ करें।"},
        "challenge": {"en": "please refund this charge or show the actual loss from my early exit (Indian Contract Act, 1872, s.74).",
                      "kn": "ಈ ಶುಲ್ಕವನ್ನು ಹಿಂತಿರುಗಿಸಿ, ಅಥವಾ ನಾನು ಬೇಗ ಖಾಲಿ ಮಾಡಿದ್ದರಿಂದ ಆದ ನಿಜವಾದ ನಷ್ಟವನ್ನು ತೋರಿಸಿ (ಭಾರತೀಯ ಒಪ್ಪಂದ ಕಾಯ್ದೆ, 1872, ಸೆಕ್ಷನ್ 74).",
                      "hi": "कृपया यह शुल्क लौटाएँ, या समय से पहले घर छोड़ने से हुआ वास्तविक नुकसान दिखाएँ (भारतीय संविदा अधिनियम, 1872, धारा 74)।"},
    },
    "painting_or_cleaning_fixed": {
        "request": {"en": "please charge painting or cleaning only for damage beyond reasonable wear and tear, judged against the dated move-in checklist (Transfer of Property Act, 1882, s.108(m)).",
                    "kn": "ಸಮಂಜಸ ಸವಕಳಿಗಿಂತ ಹೆಚ್ಚಿನ ಹಾನಿಗೆ ಮಾತ್ರ, ದಿನಾಂಕದ ಪ್ರವೇಶ ಪಟ್ಟಿಯ ಆಧಾರದ ಮೇಲೆ, ಬಣ್ಣ ಅಥವಾ ಸ್ವಚ್ಛತೆಯ ವೆಚ್ಚ ವಿಧಿಸಿ (ಆಸ್ತಿ ವರ್ಗಾವಣೆ ಕಾಯ್ದೆ, 1882, ಸೆಕ್ಷನ್ 108(m)).",
                    "hi": "कृपया पेंटिंग या सफ़ाई का शुल्क केवल सामान्य टूट-फूट से अधिक नुकसान के लिए लें, और उसे दिनांकित मूव-इन चेकलिस्ट से मिलाएँ (संपत्ति अंतरण अधिनियम, 1882, धारा 108(m))।"},
        "challenge": {"en": "please refund this deduction or share dated evidence of damage beyond reasonable wear and tear (Transfer of Property Act, 1882, s.108(m)).",
                      "kn": "ಈ ಕಡಿತವನ್ನು ಹಿಂತಿರುಗಿಸಿ, ಅಥವಾ ಸಮಂಜಸ ಸವಕಳಿಗಿಂತ ಹೆಚ್ಚಿನ ಹಾನಿಯ ದಿನಾಂಕಸಹಿತ ಪುರಾವೆಯನ್ನು ಹಂಚಿಕೊಳ್ಳಿ (ಆಸ್ತಿ ವರ್ಗಾವಣೆ ಕಾಯ್ದೆ, 1882, ಸೆಕ್ಷನ್ 108(m)).",
                      "hi": "कृपया यह कटौती लौटाएँ, या सामान्य टूट-फूट से अधिक नुकसान का दिनांकित सबूत दें (संपत्ति अंतरण अधिनियम, 1882, धारा 108(m))।"},
    },
    "notice_shortfall": {
        "request": {"en": "please agree that notice already given counts, or set the notice period to one month.",
                    "kn": "ಈಗಾಗಲೇ ನೀಡಿದ ಸೂಚನೆಯನ್ನು ಪರಿಗಣಿಸಿ, ಅಥವಾ ಸೂಚನಾ ಅವಧಿಯನ್ನು ಒಂದು ತಿಂಗಳಿಗೆ ನಿಗದಿಪಡಿಸಿ.",
                    "hi": "कृपया मान लें कि पहले दिया गया नोटिस गिना जाएगा, या नोटिस अवधि एक महीना तय करें।"},
        "challenge": {"en": "please refund this charge for the notice period, or explain how it follows from the agreement.",
                      "kn": "ಸೂಚನಾ ಅವಧಿಗಾಗಿ ವಿಧಿಸಿದ ಈ ಶುಲ್ಕವನ್ನು ಹಿಂತಿರುಗಿಸಿ, ಅಥವಾ ಇದು ಒಪ್ಪಂದದಿಂದ ಹೇಗೆ ಬರುತ್ತದೆ ಎಂದು ವಿವರಿಸಿ.",
                      "hi": "कृपया नोटिस अवधि के लिए लिया गया यह शुल्क लौटाएँ, या बताएँ कि यह समझौते के अनुसार कैसे बनता है।"},
    },
    "rent_escalation_excess": {
        "request": {"en": "please revise the yearly rent increase to 10%.",
                    "kn": "ವಾರ್ಷಿಕ ಬಾಡಿಗೆ ಹೆಚ್ಚಳವನ್ನು 10% ಕ್ಕೆ ಇಳಿಸಿ.",
                    "hi": "कृपया सालाना किराया बढ़ोतरी 10% तक सीमित करें।"},
        "challenge": {"en": "please apply the yearly rent increase only as the agreement states.",
                      "kn": "ವಾರ್ಷಿಕ ಬಾಡಿಗೆ ಹೆಚ್ಚಳವನ್ನು ಒಪ್ಪಂದದಲ್ಲಿ ಹೇಳಿರುವಂತೆ ಮಾತ್ರ ಅನ್ವಯಿಸಿ.",
                      "hi": "कृपया सालाना किराया बढ़ोतरी केवल समझौते में लिखी शर्तों के अनुसार लागू करें।"},
    },
    "wear_and_tear": {
        "request": {"en": "please confirm that reasonable wear and tear will not be deducted (Transfer of Property Act, 1882, s.108(m)).",
                    "kn": "ಸಮಂಜಸ ಸವಕಳಿಗೆ ಕಡಿತ ಮಾಡುವುದಿಲ್ಲ ಎಂದು ದೃಢೀಕರಿಸಿ (ಆಸ್ತಿ ವರ್ಗಾವಣೆ ಕಾಯ್ದೆ, 1882, ಸೆಕ್ಷನ್ 108(m)).",
                    "hi": "कृपया पुष्टि करें कि सामान्य टूट-फूट के लिए कोई कटौती नहीं होगी (संपत्ति अंतरण अधिनियम, 1882, धारा 108(m))।"},
        "challenge": {"en": "please refund this deduction: reasonable wear and tear is excepted from the tenant's restoration duty (Transfer of Property Act, 1882, s.108(m)).",
                      "kn": "ಈ ಕಡಿತವನ್ನು ಹಿಂತಿರುಗಿಸಿ: ಸಮಂಜಸ ಸವಕಳಿಗೆ ಬಾಡಿಗೆದಾರರು ಹೊಣೆಯಲ್ಲ (ಆಸ್ತಿ ವರ್ಗಾವಣೆ ಕಾಯ್ದೆ, 1882, ಸೆಕ್ಷನ್ 108(m)).",
                      "hi": "कृपया यह कटौती लौटाएँ: सामान्य टूट-फूट किरायेदार की बहाली की ज़िम्मेदारी से बाहर है (संपत्ति अंतरण अधिनियम, 1882, धारा 108(m))।"},
    },
}
OPENINGS = {
    "request": {"en": "Hello, before I sign the agreement, I request the following changes:",
                "kn": "ನಮಸ್ಕಾರ, ಒಪ್ಪಂದಕ್ಕೆ ಸಹಿ ಮಾಡುವ ಮೊದಲು ಈ ಬದಲಾವಣೆಗಳನ್ನು ಕೋರುತ್ತೇನೆ:",
                "hi": "नमस्ते, समझौते पर हस्ताक्षर करने से पहले मेरा अनुरोध है कि ये बदलाव किए जाएँ:"},
    "challenge": {"en": "Regarding the deductions from my security deposit:", "kn": "ನನ್ನ ಭದ್ರತಾ ಠೇವಣಿಯಿಂದ ಮಾಡಿದ ಕಡಿತಗಳ ಬಗ್ಗೆ:",
                  "hi": "मेरी सुरक्षा जमा राशि से की गई कटौतियों के बारे में:"},
}
CLOSINGS = {
    "request": {"en": "I am happy to sign once these changes are made. These are requests for discussion, subject to agreement and applicable law.",
                "kn": "ಈ ಬದಲಾವಣೆಗಳನ್ನು ಸೇರಿಸಿದ ನಂತರ ಒಪ್ಪಂದಕ್ಕೆ ಸಹಿ ಮಾಡುತ್ತೇನೆ. ಇವು ಚರ್ಚೆಗಾಗಿ ಇರುವ ವಿನಂತಿಗಳು, ಒಪ್ಪಂದ ಮತ್ತು ಅನ್ವಯವಾಗುವ ಕಾನೂನಿಗೆ ಒಳಪಟ್ಟಿವೆ.",
                "hi": "ये बदलाव हो जाने पर समझौते पर हस्ताक्षर किए जा सकते हैं। ये चर्चा के लिए अनुरोध हैं, जो समझौते और लागू कानून के अधीन हैं।"},
    "challenge": {"en": "Please reply in writing. I am happy to discuss any item with evidence.",
                  "kn": "ದಯವಿಟ್ಟು ಲಿಖಿತವಾಗಿ ಉತ್ತರಿಸಿ. ಪುರಾವೆಗಳೊಂದಿಗೆ ಯಾವುದೇ ಅಂಶವನ್ನು ಚರ್ಚಿಸಬಹುದು.",
                  "hi": "कृपया लिखित में उत्तर दें। सबूतों के साथ किसी भी बिंदु पर चर्चा की जा सकती है।"},
}
ASKS_NOTE = ("Fixed, reviewed sentences per clause type in English, Kannada and Hindi; the model's own wording is not translated. "
             "Native-language review is recommended.")


def _ask_letter(findings: list[dict[str, Any]], tone: str, language: str) -> str:
    """One line per finding, worded by its category; the clause reference comes from the finding."""
    stage = "request" if tone == "request" else "challenge"
    lines = [f"- {f.get('clause_ref', f.get('clause_id', '?'))}: {ASKS[f['category']][stage][language]}" for f in findings]
    parts = [OPENINGS[stage][language], *lines, CLOSINGS[stage][language]]
    if tone == "notice":  # the firmer follow-up opens with its reminder line
        parts.insert(0, HEADERS[tone][language])
    return "\n".join(parts)


def draft_message(findings: list[dict[str, Any]], tone: str = "request", language: str = "en") -> dict[str, str]:
    """Use prototype templates; arbitrary source prose is never called translated."""
    if tone not in {"request", "challenge", "notice"} or language not in {"en", "kn", "hi"}:
        raise ValueError("Choose request/challenge/notice and en/kn/hi")
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ValueError("findings must be a list of objects")
    # Agent findings carry a known category: use the clause-specific sentences.
    if findings and all(finding.get("category") in ASKS for finding in findings):
        LOGGER.info("draft_message tone=%s language=%s findings=%s", tone, language, len(findings))
        return {"text": _ask_letter(findings, tone, language), "language": language, "tone": tone, "translation_note": ASKS_NOTE}
    # Pass only structured fields to templates; no model prose is sent as if it
    # had been translated. Keep numerical preference requests where supported.
    safe = [{key: finding[key] for key in ("clause_id", "category", "rule", "limit", "direction") if key in finding}
            | {"clause_id": finding.get("clause_ref", finding.get("clause_id", "?"))}
            for finding in findings]
    messages = draft_messages(safe)
    text = messages[{"en": "english", "kn": "kannada", "hi": "hindi"}[language]]
    if tone != "request":
        text = HEADERS[tone][language] + "\n\n" + text
    LOGGER.info("draft_message tone=%s language=%s findings=%s", tone, language, len(findings))
    return {"text": text, "language": language, "tone": tone, "translation_note": messages["translation_note"]}


def send_and_schedule(message: str, approved: bool, *, today: date | None = None) -> dict[str, str]:
    """Record an approved draft and follow-up; no external delivery is configured."""
    if approved is not True:
        raise PermissionError("Explicit tenant approval is required")
    if not isinstance(message, str) or not message.strip() or len(message) > 20000:
        raise ValueError("Provide a nonempty message of at most 20,000 characters")
    id = str(uuid4())
    record = {"id": id, "message": message, "status": "scheduled", "delivery_status": "not_sent",
              "follow_up_date": ((today or date.today()) + timedelta(days=7)).isoformat()}
    SCHEDULED[id] = record.copy()
    LOGGER.info("send_and_schedule id=%s approved=true", id)
    return record
