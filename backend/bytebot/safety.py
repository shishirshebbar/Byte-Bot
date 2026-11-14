"""Narrow request markers retained without retaining credential values."""
import re
import unicodedata
from .redaction import LABEL

NEGATION = re.compile(r"\b(?:never|not|don't|do not|avoid|ignore|example|hypothetical)\b", re.I)
PATTERNS = {
    'credential_request': re.compile(r'\b(?:share|send|tell|provide|enter|give|disclose)\b[^.!?\n]{0,60}\b' + LABEL + r'\b'
                                    r'|\b' + LABEL + r'\b[^.!?\n]{0,30}\b(?:batao|bata do|bhejo|bhej do|share karo|de do)\b', re.I),
    'collect_approval': re.compile(r'\b(?:approve|accept|authorize)\b[^.!?\n]{0,60}\b(?:collect|payment) request\b', re.I),
    'remote_access': re.compile(r'\b(?:install|enable|allow|grant)\b[^.!?\n]{0,60}\bremote[ -]access\b'
                               r'|\b(?:anydesk|teamviewer|quicksupport)\b[^.!?\n]{0,30}\b(?:install|download|daalo|kar lo|karo)\b', re.I),
    'screen_sharing': re.compile(r'\b(?:enable|start|allow|share)\b[^.!?\n]{0,60}\b(?:screen sharing|your screen)\b', re.I),
    # A "refund" that is really an outgoing payment: scanning a QR or entering a PIN only ever pays out.
    'qr_payment': re.compile(r'\bscan\b[^.!?\n]{0,40}\bQR\b|\bQR\b[^.!?\n]{0,40}\b(?:scan|return|refund|receive|wapas|lauta)', re.I),
    'pin_to_receive': re.compile(r'\b(?:return|refund|receive|reverse|claim|wapas|paise? lene)\b[^.!?\n]{0,60}\b(?:enter|type|put|daalo|dalo|daal do)\b[^.!?\n]{0,30}\bPIN\b'
                                r'|\b(?:enter|type|put|daalo|dalo)\b[^.!?\n]{0,30}\bPIN\b[^.!?\n]{0,40}\b(?:receive|return|refund|reverse|claim|get the money|wapas|confirm)\b', re.I),
}


def request_markers(text):
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Cf')
    found = []
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            prefix = re.split(r'[.!?\n]', text[max(0, match.start()-70):match.start()])[-1]
            if not NEGATION.search(prefix + match.group()):
                found.append(kind)
                break
    return found
