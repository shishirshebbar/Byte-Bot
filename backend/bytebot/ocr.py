"""Local CPU OCR; images are decoded in memory and never written to disk."""
from io import BytesIO
from threading import Lock
import warnings
from PIL import Image, UnidentifiedImageError
from .settings import ROOT
import os

FILE_LIMIT = 5 * 1024 * 1024
PIXEL_LIMIT = 16_000_000
MODEL_DIR = ROOT / os.environ.get('OCR_MODEL_DIR', '.cache/easyocr')


class EvidenceError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def decode_image(data, content_type):
    if len(data) > FILE_LIMIT:
        raise EvidenceError(413, 'evidence_too_large', 'Use an image up to 5 MiB and 16 megapixels.')
    if content_type not in ('image/png', 'image/jpeg'):
        raise EvidenceError(415, 'unsupported_image', 'Use a PNG or JPEG screenshot.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                expected = 'PNG' if content_type == 'image/png' else 'JPEG'
                if image.format != expected:
                    raise EvidenceError(415, 'unsupported_image', 'The image content must match its declared type.')
                if image.width * image.height > PIXEL_LIMIT:
                    raise EvidenceError(413, 'evidence_too_large', 'Use an image up to 5 MiB and 16 megapixels.')
                if getattr(image, 'n_frames', 1) != 1:
                    raise EvidenceError(415, 'unsupported_image', 'Use a static PNG or JPEG screenshot.')
                image.load()
                rgb = image.convert('RGB')
                return rgb, {'content_type': content_type, 'width': image.width, 'height': image.height,
                             'size_bytes': len(data)}
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise EvidenceError(413, 'evidence_too_large', 'Use an image up to 5 MiB and 16 megapixels.') from None
    except (UnidentifiedImageError, OSError, ValueError):
        raise EvidenceError(422, 'invalid_image', 'This image could not be decoded.') from None


class OCRAdapter:
    def __init__(self):
        self.reader = None
        self.lock = Lock()

    def extract(self, image):
        # A busy reader yields a manual-entry fallback instead of unbounded work.
        if not self.lock.acquire(blocking=False):
            return '', 'ocr_unavailable'
        try:
            if self.reader is None:
                import easyocr
                self.reader = easyocr.Reader(['en'], gpu=False, model_storage_directory=str(MODEL_DIR),
                                             download_enabled=False, verbose=False)
            import numpy as np
            parts = self.reader.readtext(np.asarray(image), detail=1)
            text = '\n'.join(text for _, text, confidence in parts if confidence >= 0.3).strip()
            return text, None if text else 'unreadable'
        except Exception:
            return '', 'ocr_unavailable'
        finally:
            self.lock.release()


def prepare_models():
    import easyocr
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    easyocr.Reader(['en'], gpu=False, model_storage_directory=str(MODEL_DIR),
                   download_enabled=True, verbose=False)
