"""Conservative labelled-credential redaction. Evidence is always data."""
import re
import unicodedata

# Redact the entire remainder of a credential-bearing paragraph rather than trying
# to recognize just numeric codes (passwords and spoken PINs need not be numeric).
LABEL = r'(?:upi[\s_-]*pin|card[\s_-]*pin|pin|otp|one[\s-]*time[\s-]*(?:password|code)|password|passcode|cvv|cvc|access[\s_-]*code|screen[\s_-]*sharing[\s_-]*(?:code|password)|remote[\s_-]*access[\s_-]*(?:code|password))'
AFTER = re.compile(r'\b(' + LABEL + r')\b(?:(?!\n[ \t]*\n)[\s\S])*', re.IGNORECASE)
BEFORE = re.compile(r'\b[\w@#$%+\-]{3,}\s+(?:(?:is|was)\s+)?(?:(?:my|your|the)\s+)?(' + LABEL + r')\b', re.IGNORECASE)


def redact(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Cf')
    text = BEFORE.sub(lambda m: f'[REDACTED] {m.group(1)}', text)
    return AFTER.sub(lambda m: f'{m.group(1)} [REDACTED]', text).strip()
