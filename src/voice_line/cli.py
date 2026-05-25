"""Command-line interface for VoiceLine."""

import argparse

from .engine import VoiceLine


def main():
    parser = argparse.ArgumentParser(
        prog="voice-line",
        description="Person of Interest - The Machine style speech assembler",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("speak", help="Assemble text into Machine-style speech")
    sp.add_argument("text", help="Text to speak")
    sp.add_argument("-o", "--output", help="Save to .wav file instead of playing")

    mp = sub.add_parser("missing", help="Show common words not yet in the library")
    mp.add_argument("-n", "--top", type=int, default=20,
                    help="Number of words to show (default: 20)")

    sub.add_parser("stats", help="Show library statistics and coverage")

    args = parser.parse_args()
    vl = VoiceLine()

    if args.command == "speak":
        vl.speak(args.text, output=args.output)

    elif args.command == "missing":
        print(vl.stats())

    elif args.command == "stats":
        print(vl.stats())


if __name__ == "__main__":
    main()
