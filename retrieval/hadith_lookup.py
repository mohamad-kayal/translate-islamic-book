"""High-level hadith retrieval + JSON CLI (called by translation subagents)."""
import argparse
import json

from .hadith_index import HadithIndex

_INDEX = None


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = HadithIndex.load()
    return _INDEX


def match(arabic_query, min_conf=0.6):
    r = _index().match(arabic_query, min_conf=min_conf)
    return r if r is not None else {"matched": False}


def main(argv=None):
    p = argparse.ArgumentParser(description="Match an Arabic hadith matn to the dataset.")
    p.add_argument("--match", required=True)
    p.add_argument("--min-conf", type=float, default=0.6)
    args = p.parse_args(argv)
    print(json.dumps(match(args.match, args.min_conf), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
