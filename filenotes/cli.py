"""``notes`` dispatcher: a single entry point over the note subcommands.

Routes ``notes <verb> …`` to the existing per-command ``main`` functions, so
``note`` / ``ls-notes`` / ``cat-notes`` remain available as short aliases while
``notes add|ls|cat`` offers one unified interface.
"""

from __future__ import annotations

import sys
from typing import Callable, Dict, List, Optional

from . import __version__, catnotes, lsnotes, note

SUBCOMMANDS: Dict[str, Callable[[List[str]], int]] = {
    "add": note.main,
    "ls": lsnotes.main,
    "cat": catnotes.main,
}

_SUMMARY = {
    "add": "add a note to a file, folder, or recent-file selection",
    "ls": "list files with notes and show them",
    "cat": "concatenate notes into one Markdown document",
}


def _print_help(stream=None) -> None:
    stream = stream if stream is not None else sys.stdout
    print("usage: notes <command> [args...]\n", file=stream)
    print("commands:", file=stream)
    for name in SUBCOMMANDS:
        print(f"  {name:<5} {_SUMMARY[name]}", file=stream)
    print("\nEach command also has a standalone alias: note, ls-notes, cat-notes.", file=stream)
    print("Run 'notes <command> --help' for command-specific options.", file=stream)


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        _print_help(sys.stderr)
        return 1
    if argv[0] in ("-h", "--help"):
        _print_help()
        return 0
    if argv[0] == "--version":
        print(f"notes {__version__}")
        return 0

    verb, rest = argv[0], argv[1:]
    if verb not in SUBCOMMANDS:
        print(f"notes: unknown command '{verb}'\n", file=sys.stderr)
        _print_help(sys.stderr)
        return 2
    return SUBCOMMANDS[verb](rest)


if __name__ == "__main__":
    raise SystemExit(main())
