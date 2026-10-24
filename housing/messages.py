"""Deterministic multilingual drafting from structured findings, not translation."""
from __future__ import annotations

import math


_RULES = {
    "max_deposit_months": ("security deposit (months of rent)", "ಭದ್ರತಾ ಠೇವಣಿ (ತಿಂಗಳ ಬಾಡಿಗೆಯಷ್ಟು)", "सुरक्षा जमा (महीनों के किराये के बराबर)"),
    "max_notice_days": ("termination notice period (days)", "ಒಪ್ಪಂದ ಮುಕ್ತಾಯದ ಸೂಚನಾ ಅವಧಿ (ದಿನಗಳು)", "समझौता समाप्ति की सूचना अवधि (दिन)"),
    "min_notice_days": ("termination notice period (days)", "ಒಪ್ಪಂದ ಮುಕ್ತಾಯದ ಸೂಚನಾ ಅವಧಿ (ದಿನಗಳು)", "समझौता समाप्ति की सूचना अवधि (दिन)"),
    "max_rent_increase_percent": ("rent increase (%)", "ಬಾಡಿಗೆ ಹೆಚ್ಚಳ (%)", "किराये में वृद्धि (%)"),
    "max_refund_days": ("deposit refund deadline (days)", "ಠೇವಣಿ ಮರುಪಾವತಿಯ ಗಡುವು (ದಿನಗಳು)", "जमा राशि वापसी की समय सीमा (दिन)"),
    "min_entry_notice_hours": ("notice before entry (hours)", "ಪ್ರವೇಶಕ್ಕೆ ಮುಂಚಿನ ಸೂಚನೆ (ಗಂಟೆಗಳು)", "प्रवेश से पहले सूचना (घंटे)"),
}


def draft_messages(findings: list[dict], agreements: list[dict] | None = None) -> dict:
    """Use structured numerical requests; never pass arbitrary prose as translated text.

    Findings accept clause_id, category, rule, limit and optional direction.
    Agreements are original English text, returned separately for user review.
    """
    en = ["Hello, before signing the agreement, please consider the following requests:"]
    kn = ["ನಮಸ್ಕಾರ, ಒಪ್ಪಂದಕ್ಕೆ ಸಹಿ ಮಾಡುವ ಮೊದಲು ದಯವಿಟ್ಟು ಕೆಳಗಿನ ವಿನಂತಿಗಳನ್ನು ಪರಿಗಣಿಸಿ:"]
    hi = ["नमस्कार, समझौते पर हस्ताक्षर करने से पहले कृपया निम्न अनुरोधों पर विचार करें:"]
    for finding in findings:
        clause = str(finding.get("clause_id", "?"))
        rule = finding.get("rule")
        limit = finding.get("limit")
        numeric = isinstance(limit, (int, float)) and not isinstance(limit, bool) and math.isfinite(limit)
        if finding.get("category") == "preference" and rule in _RULES and numeric:
            amount = str(limit)
            labels = _RULES[rule]
            minimum = finding.get("direction", "minimum" if rule.startswith("min_") else "maximum") in {"minimum", "min"}
            en.append(f"- {clause}: Please set the {labels[0]} to {'at least' if minimum else 'no more than'} {amount}.")
            kn.append(f"- {clause}: ದಯವಿಟ್ಟು {labels[1]} {'ಕನಿಷ್ಠ' if minimum else 'ಗರಿಷ್ಠ'} {amount} ಆಗಿರಲಿ.")
            hi.append(f"- {clause}: कृपया {labels[2]} {'कम से कम' if minimum else 'अधिकतम'} {amount} रखें।")
        elif finding.get("category") in {"legal", "legal_conflict", "potential_legal_conflict"}:
            en.append(f"- {clause}: Please clarify this term with a link to the applicable official legal source before we agree.")
            kn.append(f"- {clause}: ಒಪ್ಪಿಕೊಳ್ಳುವ ಮೊದಲು ಅನ್ವಯಿಸುವ ಅಧಿಕೃತ ಕಾನೂನು ಮೂಲದ ಕೊಂಡಿಯೊಂದಿಗೆ ಈ ಷರತ್ತನ್ನು ದಯವಿಟ್ಟು ಸ್ಪಷ್ಟಪಡಿಸಿ.")
            hi.append(f"- {clause}: सहमति से पहले कृपया लागू आधिकारिक कानूनी स्रोत के लिंक के साथ इस शर्त को स्पष्ट करें।")
        else:
            en.append(f"- {clause}: Please clarify the conditions, amounts, deadlines and responsibilities in writing before we agree.")
            kn.append(f"- {clause}: ಒಪ್ಪಿಕೊಳ್ಳುವ ಮೊದಲು ಷರತ್ತುಗಳು, ಮೊತ್ತಗಳು, ಗಡುವುಗಳು ಮತ್ತು ಜವಾಬ್ದಾರಿಗಳನ್ನು ದಯವಿಟ್ಟು ಲಿಖಿತವಾಗಿ ಸ್ಪಷ್ಟಪಡಿಸಿ.")
            hi.append(f"- {clause}: सहमति से पहले कृपया शर्तें, राशियाँ, समय सीमाएँ और जिम्मेदारियाँ लिखित रूप में स्पष्ट करें।")
    if not findings:
        en.append("Please confirm the agreement terms and applicable jurisdiction before signing.")
        kn.append("ಸಹಿ ಮಾಡುವ ಮೊದಲು ಒಪ್ಪಂದದ ಷರತ್ತುಗಳು ಮತ್ತು ಅನ್ವಯಿಸುವ ನ್ಯಾಯವ್ಯಾಪ್ತಿಯನ್ನು ದಯವಿಟ್ಟು ದೃಢಪಡಿಸಿ.")
        hi.append("हस्ताक्षर करने से पहले कृपया समझौते की शर्तों और लागू क्षेत्राधिकार की पुष्टि करें।")
    en.append("These are requests for discussion, subject to agreement and applicable law.")
    kn.append("ಇವು ಚರ್ಚೆಗಾಗಿ ವಿನಂತಿಗಳು; ಪರಸ್ಪರ ಒಪ್ಪಿಗೆ ಮತ್ತು ಅನ್ವಯಿಸುವ ಕಾನೂನಿಗೆ ಒಳಪಟ್ಟಿರುತ್ತವೆ.")
    hi.append("ये चर्चा के अनुरोध हैं और आपसी सहमति तथा लागू कानून के अधीन हैं।")
    return {"english": "\n".join(en), "kannada": "\n".join(kn), "hindi": "\n".join(hi),
            "translation_note": "Deterministic language templates for structured requests, not free-form translation. Generic clarification replaces unstructured findings. Native-language review is recommended. Negotiated text is provided separately in its original language.",
            "agreements_original": [{"clause_id": str(a.get("clause_id", "?")), "text": str(a.get("text", ""))} for a in (agreements or [])]}
