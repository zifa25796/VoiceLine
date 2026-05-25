"""Command-line interface for VoiceLine."""

import argparse

from .engine import VoiceLine


def main():
    parser = argparse.ArgumentParser(
        prog="voice-line",
        description="Person of Interest - The Machine style speech assembler",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # speak
    sp = sub.add_parser("speak", help="Assemble text into Machine-style speech")
    sp.add_argument("text", help="Text to speak")
    sp.add_argument("-o", "--output", help="Save to .wav file instead of playing")

    # index
    ip = sub.add_parser("index", help="Index audio files into the word library")
    ip.add_argument("path", help="Audio file or directory to process")

    # missing
    mp = sub.add_parser("missing", help="Show common words missing from the library")
    mp.add_argument("-n", "--top", type=int, default=20, help="Number of words to show (default: 20)")

    # stats
    sub.add_parser("stats", help="Show library statistics and coverage")

    args = parser.parse_args()
    vl = VoiceLine()

    if args.command == "speak":
        missing = vl.speak(args.text, output=args.output)
        if missing:
            print(f"\nMissing from library ({len(missing)}): {', '.join(missing)}")

    elif args.command == "index":
        print(f"Indexing: {args.path}")
        result = vl.index(args.path)
        print(f"Files processed:   {result.get('files_processed', 1)}")
        print(f"Words found:       {result['words_found']}")
        print(f"Words added:       {result['words_added']}")
        print(f"Skipped (full):    {result['words_skipped_full']}")
        print(f"Skipped (empty):   {result['words_skipped_empty']}")
        if result.get("errors"):
            print(f"Errors:            {len(result['errors'])}")
            for err in result["errors"]:
                print(f"  {err['file']}: {err['error']}")

    elif args.command == "missing":
        print(vl.stats())

    elif args.command == "stats":
        print(vl.stats())


if __name__ == "__main__":
    main()
