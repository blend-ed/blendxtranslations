#!/usr/bin/env python3
"""
Fix invalid Punjabi (pa) placeholders in translation files.

In .po files (python-brace-format): Placeholders like {ਮੋਡ} must use exact
English identifiers from msgid (e.g. {mode}) because Python substitutes at runtime.

In .json files (ICU MessageFormat): Variables like {ਆਬਜੈਕਟ} must match
source (e.g. {object}) for formatjs/react-intl interpolation.

Usage:
    python scripts/fix_punjabi_placeholders.py [--dry-run] [--po-only] [--json-only]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Punjabi placeholder -> English placeholder mapping
# Built from known fixes across pa locale files
PA_TO_EN_PLACEHOLDER_MAP = {
    # Common
    "ਆਬਜੈਕਟ": "object",
    "ਵਸਤੂ": "object",
    "ਪੂਰਾ": "completed",
    "ਕੁੱਲ": "total",
    "ਨੰਬਰ": "number",
    "ਸੰਕੇਤ": "hint",
    "ਵਜ਼ਨ": "weight",
    "ਸਕੋਰ_ਸਟ੍ਰਿੰਗ": "score_string",
    "ਘੱਟੋ-ਘੱਟ": "min",
    "ਵੱਧ ਤੋਂ ਵੱਧ": "max",
    "ਲੇਬਲ": "label",
    "ਪੀਅਰ_ਇੰਡੈਕਸ": "peer_index",
    "ਲਾਈਨ": "line",
    "ਆਈਟਮ": "item",
    "ਗਿਣਤੀ": "count",
    "ਸੰਗਠਨ": "organization",
    "ਖਰੀਦ_ਕਾਰਵਾਈ": "purchase_action",
    "ਪਹਿਲੀਆਂ ਚੀਜ਼ਾਂ": "firstItems",
    "ਆਖਰੀ ਚੀਜ਼": "lastItem",
    "ਪਹਿਲਾ_ਸੰਗਠਨ": "first_org",
    "ਦੂਜਾ_ਸੰਗਠਨ": "second_org",
    "ਮਹੀਨਾ": "month",
    "ਸਾਲ": "year",
    "ਕੁੰਜੀ": "key",
    "ਆਈਡੀ": "id",
    "ਕਿਸਮ": "type",
    "ਸਿਰਲੇਖ": "title",
    "ਲਿੰਕ_ਸ਼ੁਰੂਆਤ": "link_start",
    "ਸਾਡੇ ਨਾਲ ਸੰਪਰਕ ਕਰੋ_ਈਮੇਲ": "contact_us_email",
    "ਲਿੰਕ_ਮੱਧਮ": "link_middle",
    "ਲਿੰਕ_ਅੰਤ": "link_end",
    "ਮੁੱਲ": "value",
    "ਘੰਟੇ_ਨੰਬਰ": "num_hours",
    # edx-platform / common
    "ਪਿਛਲੇ_ਸਮੂਹ": "previous_groups",
    "ਮੌਜੂਦਾ_ਸਮੂਹ": "current_group",
    "ਪ੍ਰੋਫਾਈਲ_ਨਾਮ": "profile_name",
    "ਕੋਰਸ": "course",
    "ਵੇਰਵੇ": "details",
    "ਸੈਕਸ਼ਨ_ਜਾਂ_ਸਬਸੈਕਸ਼ਨ": "section_or_subsection",
    "ਡਿਸਪਲੇਅ_ਨਾਮ": "display_name",
    "ਮੁਦਰਾ_ਪ੍ਰਤੀਕ": "currency_symbol",
    "ਕੀਮਤ": "price",
    "ਸੰਬੰਧਤ": "related",
    "ਪੂਰਨ": "full",
    "ਰਿਸ਼ਤੇਦਾਰ": "related",
    "ਤਾਰੀਖ": "date",
    "ਸਮੂਹ": "group",
    "ਵਿਦਿਆਰਥੀ": "student",
    "ਕਤਾਰ": "row",
    "ਉਪਭੋਗਤਾ": "user",
    "ਕੋਸ਼ਿਸ਼ਾਂ": "attempts",
    "ਕਾਰਵਾਈ": "action",
    "ਸਫਲ": "succeeded",
    "ਕੋਸ਼ਿਸ਼ ਕੀਤੇ": "attempted",
    "ਕੋਸ਼ਿਸ਼ ਕੀਤੀ ਗਈ": "attempted",
    "ਕੋਸ਼ਿਸ਼": "attempt",
    "ਛੱਡਿਆ": "skipped",
    "ਪਹਿਲਾ_ਪ੍ਰੋਵਾਈਡਰ": "first_provider",
    "ਦੂਜਾ_ਪ੍ਰੋਵਾਈਡਰ": "second_provider",
    "ਦੇਸ਼": "country",
    "ਘੱਟੋ": "min",
    "ਹੈਡਰ_ਓਪਨ": "header_open",
    "ਹੈਡਰ_ਕਲੋਜ਼": "header_close",
    "ਬਾਡੀ": "body",
    "ਸਿਰਲੇਖ_ਖੁੱਲ੍ਹਣਾ": "title_open",
    "ਸਿਰਲੇਖ_ਬੰਦ": "title_close",
    "ਅਸਾਈਨਮੈਂਟ": "assignment",
    "ਸੂਚਕਾਂਕ": "index",
    "ਪਿਛਲੇ_ਸੰਕੇਤ": "prev_hint",
    "ਸੂਚੀ_ਸ਼ੁਰੂਆਤ_ਟੈਗ": "list_start_tag",
    "ਮਜ਼ਬੂਤ_ਟੈਕਸਟ": "bold_text",
    "ਸੰਕੇਤ_ਟੈਕਸਟ": "hint_text",
    "ਪ੍ਰਗਤੀ": "progress",
    "ਭਾਰ": "weight",
    "ਭਾਰ_ਪ੍ਰਤੀਸ਼ਤ": "weight_percent",
    "ਪ੍ਰਤੀਸ਼ਤ": "percent",
    "ਅਸਲ": "actual",
    "ਹੋਮਪੇਜ": "homepage",
    "ਨਾਮ": "name",
    "ਈਮੇਲ": "email",
    "ਸੁਨੇਹਾ": "message",
    "ਟੈਗਸ": "tags",
    "ਪੁਆਇੰਟ": "points",
    "ਕਮਾਇਆ": "earned",
    "ਸੰਭਵ": "possible",
    "ਲੇਬਲ": "label",
    "ਸਥਿਤੀ": "status",
    "ਪੈਰਾ": "paragraph",
    "ਕ੍ਰਮ": "order",
    "ਆਰਡਰ": "order",
    "ਹਾਈਲਾਈਟ_ਇੰਡੈਕਸ": "highlight_index",
    "ਪਲੇਟਫਾਰਮ": "platform",
    "ਸੈਸ਼ਨ ਤਾਰੀਖਾਂ": "sessionDates",
    "ਪ੍ਰੋਗਰਾਮ": "program",
    "ਲਿਸਟਪ੍ਰਾਈਸ": "listPrice",
    "ਮੁਦਰਾ": "currency",
    "ਆਈਕਨ": "icon",
    "ਸਾਈਟ": "site",
    "ਫਾਈਲ": "file",
    "ਸੰਖਿਆ": "count",
    "ਪੁਰਾਣੀ ਕੀਮਤ": "oldPrice",
    "ਨਵੀਂ ਕੀਮਤ": "newPrice",
    "ਕਮਾਏ": "earned",
    "ਪੂਰਾ_ਨਾਮ": "fullName",
    "ਮਿਤੀ": "date",
    "ਕੰਪੋਨੈਂਟ_ਟਾਈਪ": "component_type",
    "ਘੰਟੇ": "hours",
    "ਮਿੰਟ": "minutes",
    "ਸਕਿੰਟ": "seconds",
    "ਯੂਨਿਟ": "unit",
    "ਸ਼ੁਰੂ": "start",
    "ਪ੍ਰੋਸੈਸਰ": "processor",
    "ਯੂਨੀਕ ਆਈਡੀ": "uniqueId",
    "ਵਿਲੱਖਣ ਆਈਡੀ": "uniqueId",
    "ਯੂਨਿਕ ਆਈਡੀ": "uniqueId",
    "ਨਿਰਦੇਸ਼ ਸਪੈਨਸਟਾਰਟ": "instructionSpanStart",
    "ਵੀਡੀਓਇਮੇਜਰਿਜ਼ੋਲੂਸ਼ਨ": "videoImageResolution",
    "ਲਾਈਨਬ੍ਰੇਕ": "linebreak",
    "ਵੀਡੀਓਇਮੇਜਸਪੋਰਟੇਡਫਾਈਲਫਾਰਮੈਟ": "videoImageSupportedFileFormat",
    "ਸਪੈਨਐਂਡ": "spanEnd",
    "ਇਨਪੁਟਪਲੇਸਹੋਲਡਰ": "inputPlaceholder",
    "ਵਾਧੂ ਵੇਰਵੇ ਲੇਬਲ": "additionalDetailsLabel",
    "ਵਾਧੂ ਵੇਰਵੇ ਵਿਕਲਪ": "additionalDetailsOption",
    "ਫੀਡਬੈਕਸੈਂਟ ਮੈਸੇਜ": "feedbackSentMessage",
    "ਪ੍ਰੋਂਪਟ": "prompt",
    "ਸਬਮਿਟਬਟਨਲੇਬਲ": "submitButtonLabel",
    "ਧੰਨਵਾਦ ਸੁਨੇਹਾ": "thankYouMessage",
    "ਟ੍ਰਾਂਸਕ੍ਰਿਪਟਗਿਣਤੀ": "transcriptCount",
    "ਟ੍ਰਾਂਸਕ੍ਰਿਪਟ": "transcript",
    "ਹਫ਼ਤਿਆਂ ਦੀ ਗਿਣਤੀ": "weeksCount",
    "ਹਫ਼ਤਾ": "week",
    "ਹਫ਼ਤੇ": "weeks",
    "ਸੰਖਿਆ ਕੋਰਸ": "courseCount",
    "ਹੁਨਰ": "skill",
    "ਤੀਰ": "arrow",
    "ਵਧਾਈਆਂ": "congratulations",
    "ਸਾਈਟਨੇਮ": "siteName",
    "ਨੈੱਟਵਰਕ": "network",
    "ਮੌਜੂਦਾ": "current",
    "ਕੀਤਾ": "completed",
    "ਲੋੜੀਂਦਾ": "required",
    "ਘਾਤਕ ਵਾਕ-ਨਿਰਮਾਣ": "exponentWord",
    "ਨੋਟੇਸ਼ਨਸੈਂਟੈਕਸ": "notationSyntax",
    "ਗਲਤੀ": "error",
    "ਚੇਂਜਐਕਟਿਵਐਂਟਰਪ੍ਰਾਈਜ਼": "changeActiveEnterprise",
    "ਵਰਣਨ": "description",
    "ਅਸਾਈਨਮੈਂਟਡਿਊ": "assignmentDue",
    "ਸਾਈਨਇਨ": "signIn",
    "ਰਜਿਸਟਰ": "register",
    "ਜੀ ਆਇਆਂ ਨੂੰ": "welcome",
    "ਗਤੀਵਿਧੀਗਿਣਤੀ": "activityCount",
    "ਗਤੀਵਿਧੀਆਂ": "activities",
    "ਮਿੰਟਗਿਣਤੀ": "minutesCount",
    "ਪੁੱਛਗਿੱਛ": "query",
    "ਪੂਰੀ ਗਲਤੀ": "fullError",
    "ਸਮਾਂ": "time",
    "ਲਿੰਕ": "link",
    "ਸਹਾਇਤਾ ਸਥਿਤੀ": "supportStatus",
    "ਸਹਾਇਕ ਟੈਕਸਟ": "helperText",
    "ਪੂਰਵਦਰਸ਼ਨ ਵਰਣਨ": "previewDescription",
    "ਗਰੁੱਪ ਫੀਡਬੈਕ": "groupFeedback",
    "ਸੰਕੇਤ": "hint",
    "ਰੈਂਡਮਾਈਜ਼ੇਸ਼ਨ": "randomization",
    "ਕੋਸ਼ਿਸ਼ਾਂ": "attempts",
    "ਭਾਰ": "weight",
    "ਸਮਾਂ": "time",
    "ਸਥਿਤੀ": "status",
    "ਨਾਮ": "name",
    "ਹੈਡਿੰਗਟਾਈਟਲ": "headingTitle",
    "ਕੋਰਸਨਾਮ": "courseName",
    "ਸਾਈਟਨਾਮ": "siteName",
    "ਸ਼੍ਰੇਣੀ": "category",
    "ਇੰਡੈਕਸ": "index",
    "ਸਿਰਲੇਖ": "title",
    "ਲੁਕਾਓ": "hide",
    "ਈਮੇਲ": "email",
    "ਐਕਸ਼ਨਟਾਈਪ": "actionType",
    "ਚੁਣਿਆ ਹੋਇਆ ਰੋਅਕਾਊਂਟ": "selectedRowCount",
    "ਫਾਈਲਟਾਈਪ": "fileType",
    "ਸੁਨੇਹਾ": "message",
    "ਲੇਨ": "len",
    "ਆਈਡੀ": "id",
    # Additional mappings from remaining files
    "ਸੰਕੇਤ_ਗਿਣਤੀ": "hint_count",
    "ਸੰਕੇਤ_ਨੰਬਰ": "hint_number",
    "ਹਾਈਪਰਲਿੰਕ": "hyperlink",
    "ਸ਼੍ਰੇਣੀਟੈਕਸਟ": "categoryText",
    "ਲੇਨ": "len",
    "ਬੱਚੇ": "children",
    "ਕੰਟੇਨਰਟਾਈਪ": "containerType",
    "ਰਿਫ੍ਰੈਸ਼": "refresh",
    "ਟ੍ਰਾਂਸਕ੍ਰਿਪਟਕਾਉਂਟ": "transcriptCount",
    "ਕੁੱਲ ਭਾਗ": "totalComponents",
}

# Regex to find {punjabi} or {punjabi:format} placeholders (Gurmukhi: U+0A00 to U+0A7F)
# Captures: (1) name, (2) optional format specifier like :.2%
PUNJABI_PLACEHOLDER_RE = re.compile(r"\{([਀-੿][਀-੿\s\-_]*?)(:[^}]*)?\}")


def fix_po_file(filepath: Path, dry_run: bool = False) -> int:
    """Fix invalid placeholders in a .po file. Returns count of replacements."""
    content = filepath.read_text(encoding="utf-8")
    original = content
    replacements = 0

    def replace_punjabi(match):
        nonlocal replacements
        pa_placeholder = match.group(1).strip()
        format_spec = match.group(2) or ""  # e.g. ":.2%"
        en_placeholder = PA_TO_EN_PLACEHOLDER_MAP.get(pa_placeholder)
        if en_placeholder:
            replacements += 1
            return f"{{{en_placeholder}{format_spec}}}"
        return match.group(0)

    content = PUNJABI_PLACEHOLDER_RE.sub(replace_punjabi, content)

    if content != original and not dry_run:
        filepath.write_text(content, encoding="utf-8")

    return replacements


def fix_json_file(filepath: Path, dry_run: bool = False) -> int:
    """Fix invalid placeholders in a pa.json file. Returns count of replacements."""
    content = filepath.read_text(encoding="utf-8")
    original = content
    replacements = 0

    def replace_punjabi(match):
        nonlocal replacements
        pa_placeholder = match.group(1).strip()
        format_spec = match.group(2) or ""  # e.g. ":.2%"
        en_placeholder = PA_TO_EN_PLACEHOLDER_MAP.get(pa_placeholder)
        if en_placeholder:
            replacements += 1
            return f"{{{en_placeholder}{format_spec}}}"
        return match.group(0)

    content = PUNJABI_PLACEHOLDER_RE.sub(replace_punjabi, content)

    if content != original and not dry_run:
        filepath.write_text(content, encoding="utf-8")

    return replacements


def main():
    parser = argparse.ArgumentParser(description="Fix invalid Punjabi placeholders in pa locale files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without writing")
    parser.add_argument("--po-only", action="store_true", help="Only process .po files")
    parser.add_argument("--json-only", action="store_true", help="Only process .json files")
    parser.add_argument("--translations-dir", default="translations", type=Path, help="Translations root directory")
    args = parser.parse_args()

    translations_dir = args.translations_dir
    if not translations_dir.exists():
        print(f"Error: {translations_dir} not found", file=sys.stderr)
        sys.exit(1)

    total_po = 0
    total_json = 0

    if not args.json_only:
        for po_file in translations_dir.rglob("pa/LC_MESSAGES/*.po"):
            count = fix_po_file(po_file, dry_run=args.dry_run)
            if count > 0:
                total_po += count
                mode = "(dry-run) " if args.dry_run else ""
                print(f"{mode}{po_file}: {count} replacements")

    if not args.po_only:
        for json_file in translations_dir.rglob("**/messages/pa.json"):
            count = fix_json_file(json_file, dry_run=args.dry_run)
            if count > 0:
                total_json += count
                mode = "(dry-run) " if args.dry_run else ""
                print(f"{mode}{json_file}: {count} replacements")

    total = total_po + total_json
    if args.dry_run and total > 0:
        print(f"\nDry run: would fix {total} placeholders total")
    elif total > 0:
        print(f"\nFixed {total} placeholders total")
    else:
        print("No invalid Punjabi placeholders found (or all already fixed)")


if __name__ == "__main__":
    main()
