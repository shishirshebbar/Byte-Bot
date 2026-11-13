import argparse
import sys
from .settings import DATABASE_URL
from .migrate import migrate
from .seeds import seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed", "ocr-prepare"])
    args = parser.parse_args()
    try:
        if args.command == 'ocr-prepare':
            from .ocr import prepare_models
            prepare_models()
        else:
            {"migrate": migrate, "seed": seed}[args.command](DATABASE_URL)
    except Exception:
        print(f"{args.command} failed; check local dependencies, configuration, and network availability.", file=sys.stderr)
        return 1
    print(f"{args.command} complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
