"""Synthetic screenshots only; no real messages or credentials."""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


def screenshot(readable=True, format='PNG', size=(1100, 280)):
    image = Image.new('RGB', size, 'white')
    if readable:
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=36)
        draw.text((35, 45), 'Please return INR 5000 today.', fill='black', font=font)
        draw.text((35, 120), 'Send to demo.receiver@upi', fill='black', font=font)
    output = BytesIO()
    image.save(output, format=format)
    image.close()
    return output.getvalue()


def scenario_screenshot(scenario='B'):
    import sys
    import textwrap
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bytebot.fixtures import SCENARIOS
    text = SCENARIOS[scenario]['text']
    if not text:
        raise ValueError('This scenario has no message screenshot')
    lines = textwrap.wrap(text, width=48)
    image = Image.new('RGB', (1150, 70 + len(lines) * 65), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    for index, line in enumerate(lines):
        draw.text((35, 35 + index * 65), line, fill='black', font=font)
    output = BytesIO()
    image.save(output, format='PNG')
    image.close()
    return output.getvalue()


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Generate a synthetic demo message screenshot only.')
    parser.add_argument('--scenario', choices=list('ABCE'), default='B')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(scenario_screenshot(args.scenario))
    print(f'Wrote synthetic Scenario {args.scenario} screenshot: {args.output}')
