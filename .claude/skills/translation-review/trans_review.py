#!/usr/bin/env python3
"""Translation review helper for the openedx-translations repo.

Subcommands:
  scan [--base REF] [--out DIR]
      Find new/changed keys in every translations/*/src/i18n/messages/<lang>.json
      versus REF (default HEAD). For each language write DIR/<lang>.json mapping
      "app::key" -> {"en": <source>, "tr": <translation>}. Also runs the ICU
      structural check and prints any broken placeholders. Prints the language
      list and per-language key counts.

  validate [--base REF]
      JSON-validity + ICU-placeholder check on all changed translation files.
      ICU check compares each translated value's placeholder argument names and
      plural/select selectors against the English source. Exit code 1 on errors.

  apply --in DIR
      Apply DIR/<lang>.fixes.json files. Each is "app::key" -> {"new": ...}.
      Writes files back sorted by key, UTF-8, indent 2, no trailing newline
      (matching repo format). Re-runs validate afterwards.

ICU rule: placeholder argument names ({name}), the plural/select keywords, the
selector keywords (one/other/few/many/zero/two), and braces/commas MUST stay
identical to the English source. Only human-readable text is translated.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip()
MSG_GLOB = os.path.join(ROOT, "translations", "*", "src", "i18n", "messages")
VALID_SEL = {"zero", "one", "two", "few", "many", "other"}
SUBMSG = {"plural", "select", "selectordinal"}


def git_show(ref, relpath):
    try:
        return json.loads(subprocess.check_output(
            ["git", "show", f"{ref}:{relpath}"], cwd=ROOT, stderr=subprocess.DEVNULL))
    except Exception:
        return {}


def rel(path):
    return os.path.relpath(path, ROOT)


def apps():
    return sorted(glob.glob(MSG_GLOB))


def langs_in(base):
    out = []
    for f in sorted(glob.glob(os.path.join(base, "*.json"))):
        lang = os.path.basename(f)[:-5]
        if not lang.startswith("en"):
            out.append(lang)
    return out


def parse_icu(s):
    """Return (arg_names:set, selectors:set). Raises on malformed nesting."""
    args, sels = set(), set()

    def block(i):
        while i < len(s):
            c = s[i]
            if c == '}':
                return i
            if c == '{':
                j = i + 1
                name = ''
                while j < len(s) and s[j] not in ',}':
                    name += s[j]
                    j += 1
                args.add(name.strip())
                if j >= len(s) or s[j] == '}':
                    i = j + 1
                    continue
                k = j + 1
                typ = ''
                while k < len(s) and s[k] != ',':
                    typ += s[k]
                    k += 1
                typ = typ.strip()
                p = k + 1
                if typ not in SUBMSG:
                    d = 0
                    q = i
                    while q < len(s):
                        if s[q] == '{':
                            d += 1
                        elif s[q] == '}':
                            d -= 1
                            if d == 0:
                                q += 1
                                break
                        q += 1
                    i = q
                    continue
                while p < len(s):
                    while p < len(s) and s[p] in ' \t\r\n':
                        p += 1
                    if p < len(s) and s[p] == '}':
                        p += 1
                        break
                    sel = ''
                    while p < len(s) and s[p] != '{':
                        sel += s[p]
                        p += 1
                    raw = sel.strip()
                    # `=N` explicit-value selectors (e.g. `=0 {today}`) are valid
                    # ICU/react-intl and need no plural-keyword check.
                    if not (raw.startswith('=') and raw[1:].isdigit()):
                        sels.add(raw.lstrip('='))
                    p = block(p + 1)
                    if p < len(s) and s[p] == '}':
                        p += 1
                i = p
                continue
            i += 1
        return i

    block(0)
    return args, sels


def changed_keys(base):
    """Yield (app_base_dir, app_name, lang, key, en_val, tr_val) for new/changed."""
    for base_dir in apps():
        app = base_dir.split(os.sep)[-4]
        en_path = os.path.join(base_dir, "en.json")
        if not os.path.exists(en_path):
            continue
        en = json.load(open(en_path))
        for lang in langs_in(base_dir):
            path = os.path.join(base_dir, f"{lang}.json")
            cur = json.load(open(path))
            old = git_show(base, rel(path))
            for k in cur:
                if k not in old or cur[k] != old.get(k):
                    yield base_dir, app, lang, k, en.get(k, ""), cur[k]


def icu_errors(base):
    errs = []
    for base_dir, app, lang, k, en_val, tr in changed_keys(base):
        if '{' not in tr:
            continue
        if tr.count('{') != tr.count('}'):
            errs.append(f"UNBALANCED {lang} {app}::{k} | {tr}")
            continue
        try:
            ea, _ = parse_icu(en_val)
            a, sl = parse_icu(tr)
        except Exception as e:
            errs.append(f"PARSEFAIL {lang} {app}::{k}: {e} | {tr}")
            continue
        if ea - a:
            errs.append(f"ARG-MISSING {lang} {app}::{k} expected {sorted(ea)} got {sorted(a)} | {tr}")
        if sl - VALID_SEL:
            errs.append(f"BAD-SELECTOR {lang} {app}::{k} {sorted(sl - VALID_SEL)} | {tr}")
        if sl and 'other' not in sl:
            errs.append(f"NO-OTHER {lang} {app}::{k} | {tr}")
    return errs


def cmd_scan(args):
    os.makedirs(args.out, exist_ok=True)
    per_lang = {}
    for base_dir, app, lang, k, en_val, tr in changed_keys(args.base):
        per_lang.setdefault(lang, {})[f"{app}::{k}"] = {"en": en_val, "tr": tr}
    for lang, data in sorted(per_lang.items()):
        json.dump(data, open(os.path.join(args.out, f"{lang}.json"), "w"),
                  ensure_ascii=False, indent=1)
    print(f"languages: {sorted(per_lang)}")
    for lang in sorted(per_lang):
        print(f"  {lang}: {len(per_lang[lang])} new/changed keys -> {args.out}/{lang}.json")
    errs = icu_errors(args.base)
    print(f"\nICU placeholder breakage: {len(errs)}")
    for e in errs:
        print("  " + e)


def cmd_validate(args):
    changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT).decode().split()
    bad_json = 0
    for f in changed:
        if not f.endswith(".json"):
            continue
        try:
            json.load(open(os.path.join(ROOT, f)))
        except Exception as e:
            print(f"INVALID JSON {f}: {e}")
            bad_json += 1
    errs = icu_errors(args.base)
    print(f"JSON invalid: {bad_json} | ICU errors: {len(errs)}")
    for e in errs:
        print("  " + e)
    sys.exit(1 if (bad_json or errs) else 0)


def cmd_apply(args):
    total = 0
    for ff in sorted(glob.glob(os.path.join(args.indir, "*.fixes.json"))):
        lang = os.path.basename(ff)[:-len(".fixes.json")]
        fixes = json.load(open(ff))
        by_app = {}
        for ck, info in fixes.items():
            app, key = ck.split("::", 1)
            by_app.setdefault(app, {})[key] = info["new"]
        for app, kv in by_app.items():
            path = os.path.join(ROOT, "translations", app, "src", "i18n", "messages", f"{lang}.json")
            obj = json.load(open(path))
            for k, v in kv.items():
                if k not in obj:
                    print(f"WARN missing {lang} {app}::{k}")
                    continue
                obj[k] = v
                total += 1
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"applied {total} fixes")
    cmd_validate(argparse.Namespace(base=args.base))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--base", default="HEAD"); s.add_argument("--out", default="/tmp/trev"); s.set_defaults(func=cmd_scan)
    v = sub.add_parser("validate"); v.add_argument("--base", default="HEAD"); v.set_defaults(func=cmd_validate)
    a = sub.add_parser("apply"); a.add_argument("--in", dest="indir", default="/tmp/trev"); a.add_argument("--base", default="HEAD"); a.set_defaults(func=cmd_apply)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
