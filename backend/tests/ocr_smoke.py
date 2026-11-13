"""Run real CPU OCR against synthetic images, without persisting images."""
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bytebot.ocr import OCRAdapter, decode_image, MODEL_DIR
from synthetic_images import screenshot

reader = OCRAdapter()
for readable in (True, False):
    image, _ = decode_image(screenshot(readable), 'image/png')
    started = perf_counter()
    text, notice = reader.extract(image)
    image.close()
    elapsed = perf_counter() - started
    if readable:
        assert notice is None and 'return' in text.lower() and '5000' in text, (text, notice)
    else:
        assert text == '' and notice == 'unreadable', (text, notice)
    print(f'PASS: {"legible" if readable else "unreadable"} synthetic screenshot; {elapsed:.2f}s; CPU English; models={MODEL_DIR.name}')
