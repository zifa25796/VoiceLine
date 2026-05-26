"""命令行接口：speak / list / missing / stats。
Command-line interface for VoiceLine."""

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

    lp = sub.add_parser("list", help="Browse words in the library")
    lp.add_argument("-s", "--search", default="", help="Filter by keyword (LIKE)")
    lp.add_argument("-n", "--limit", type=int, default=50, help="Results per page")
    lp.add_argument("-p", "--page", type=int, default=1, help="Page number")
    lp.add_argument("--sort", default="word_text",
                    choices=["word_text", "clips", "quality_score", "created_at"],
                    help="Sort order")

    mp = sub.add_parser("missing", help="Show common words not yet in the library")
    mp.add_argument("-n", "--top", type=int, default=20,
                    help="Number of words to show (default: 20)")

    sub.add_parser("stats", help="Show library statistics and coverage")

    args = parser.parse_args()
    vl = VoiceLine()

    if args.command == "speak":
        vl.speak(args.text, output=args.output)

    elif args.command == "list":
        offset = (args.page - 1) * args.limit
        rows, total = vl.list_words(
            search=args.search, limit=args.limit, offset=offset,
            sort_by=args.sort,
        )
        pages = (total + args.limit - 1) // args.limit
        print(f"Words in library: {total}  (page {args.page}/{pages})\n")
        print(f"{'word':<24} {'clips':>6} {'quality':>8}  {'created'}")
        print("-" * 60)
        for r in rows:
            print(f"{r['word_text']:<24} {r['clip_count']:>6} {r['avg_quality']:>8.3f}  {r['latest_created']}")
        if pages > 1:
            print(f"\nPage {args.page}/{pages}  (--page N for more)")

    elif args.command in ("missing", "stats"):
        print(vl.stats())


if __name__ == "__main__":
    main()
