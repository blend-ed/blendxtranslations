#!/usr/bin/env python3
"""
Fix msgid/msgstr newline structure mismatches in .po files.

When msgid starts with '\\n', msgstr must also start with '\\n' for msgfmt to accept.
Also fixes python-format placeholders with Punjabi names (%(ਪੰਜਾਬੀ)s -> %(english)s).

Usage:
    workon ulmo_dev  # or: source ~/.virtualenvs/dev-ulmo/bin/activate
    python scripts/fix_po_newline_structure.py [--dry-run] [path/to/file.po]
"""

import argparse
import re
import sys
from pathlib import Path

# Python-format: %(punjabi_name)s -> %(english_name)s
PYFORMAT_PA_TO_EN = {
    "ਸ਼ੁਰੂਆਤੀ_ਟੈਗ": "start_tag",
    "ਸਿਰਲੇਖ": "title",
    "ਅੰਤ_ਟੈਗ": "end_tag",
    "ਸ਼ੁਰੂਆਤੀ_ਗ੍ਰੇਡ_ਟੈਗ": "start_grade_tag",
    "ਗ੍ਰੇਡ": "grade",
    "ਸਮੀਖਿਆ_ਨੰਬਰ": "step_number",
    "ਟਿੱਪਣੀਆਂ": "comments",
    "ਸਿੱਖਿਆਰਥੀ": "student",
}

PYFORMAT_PUNJABI_RE = re.compile(r"%\(([਀-੿][਀-੿\s\-_]*?)\)s")


def fix_pyformat_in_string(s: str) -> tuple[str, int]:
    """Replace Punjabi python-format placeholders. Returns (new_string, count)."""
    count = 0

    def replace(match):
        nonlocal count
        pa_name = match.group(1).strip()
        en_name = PYFORMAT_PA_TO_EN.get(pa_name)
        if en_name:
            count += 1
            return f"%({en_name})s"
        return match.group(0)

    return PYFORMAT_PUNJABI_RE.sub(replace, s), count


def process_file(filepath: Path, dry_run: bool = False) -> tuple[int, int]:
    """Process a .po file. Returns (newline_fixes, pyformat_fixes)."""
    try:
        import polib
    except ImportError:
        print("Error: polib required. Run: workon ulmo_dev && pip install polib", file=sys.stderr)
        sys.exit(1)

    po = polib.pofile(filepath)
    newline_count = 0
    pyformat_count = 0

    for entry in po:
        msgid = entry.msgid
        if not msgid:
            continue
        msgid_str = msgid if isinstance(msgid, str) else "".join(msgid)

        # Fix newline: when msgid starts with \n, msgstr must too
        if msgid_str.startswith("\n"):
            if entry.msgstr_plural:
                for idx, msgstr in entry.msgstr_plural.items():
                    if msgstr and not msgstr.startswith("\n"):
                        entry.msgstr_plural[idx] = "\n" + msgstr
                        newline_count += 1
                    if msgstr:
                        fixed, n = fix_pyformat_in_string(entry.msgstr_plural[idx])
                        if n > 0:
                            entry.msgstr_plural[idx] = fixed
                            pyformat_count += n
            elif entry.msgstr:
                if not entry.msgstr.startswith("\n"):
                    entry.msgstr = "\n" + entry.msgstr
                    newline_count += 1
                fixed, n = fix_pyformat_in_string(entry.msgstr)
                if n > 0:
                    entry.msgstr = fixed
                    pyformat_count += n

        # Fix pyformat in all entries (including those without leading \n)
        elif entry.msgstr:
            fixed, n = fix_pyformat_in_string(entry.msgstr)
            if n > 0:
                entry.msgstr = fixed
                pyformat_count += n
        if entry.msgstr_plural:
            for idx in entry.msgstr_plural:
                msgstr = entry.msgstr_plural[idx]
                if msgstr:
                    fixed, n = fix_pyformat_in_string(msgstr)
                    if n > 0:
                        entry.msgstr_plural[idx] = fixed
                        pyformat_count += n

    if not dry_run and (newline_count > 0 or pyformat_count > 0):
        po.save()

    return newline_count, pyformat_count


def main():
    parser = argparse.ArgumentParser(description="Fix msgid/msgstr newline structure in .po files")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("files", nargs="*", type=Path, help=".po files to fix")
    args = parser.parse_args()

    if args.files:
        files = [Path(f) for f in args.files if Path(f).exists()]
    else:
        base = Path("translations/edx-ora2/openassessment/conf/locale/pa/LC_MESSAGES/django.po")
        files = [base] if base.exists() else []

    if not files:
        print("No files to process. Specify path or run from repo root.", file=sys.stderr)
        sys.exit(1)

    total_newline = 0
    total_pyformat = 0
    for f in files:
        n, p = process_file(f, dry_run=args.dry_run)
        total_newline += n
        total_pyformat += p
        if n or p:
            mode = "(dry-run) " if args.dry_run else ""
            print(f"{mode}{f}: {n} newline fixes, {p} pyformat fixes")

    if args.dry_run and (total_newline or total_pyformat):
        print(f"\nDry run: would apply {total_newline} newline + {total_pyformat} pyformat fixes")
    elif total_newline or total_pyformat:
        print(f"\nApplied {total_newline} newline + {total_pyformat} pyformat fixes")


if __name__ == "__main__":
    main()
