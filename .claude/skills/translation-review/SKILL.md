---
name: translation-review
description: Review machine-translated i18n strings in this openedx-translations repo for accuracy, fix mistakes, and commit. Use when the user adds/regenerates translation JSON (translations/*/src/i18n/messages/<lang>.json), mentions Google/Azure-translated files, asks to "check translations", "review translation accuracy", validate ICU placeholders, or fix/commit translation updates.
---

# Translation review

Reviews new or changed translation strings against the English source, catches
the two failure classes machine translation produces — **broken ICU
placeholders** and **wrong meaning** — applies fixes, and commits.

The helper script `trans_review.py` (next to this file) does the mechanical
detection/validation/apply. The meaning review is done by per-language subagents.

## Workflow

### 1. Scan
Run the scanner to find new/changed keys and dump per-language review files, and
to immediately surface any ICU placeholder breakage:

```
python3 .claude/skills/translation-review/trans_review.py scan --base HEAD --out /tmp/trev
```

`--base` is the git ref to diff against (default `HEAD`; use a commit SHA to
review only what changed since then). It writes `/tmp/trev/<lang>.json`, each a
map of `"app::key" -> {"en": <source>, "tr": <translation>}`, and prints any
broken placeholders.

### 2. Fix ICU breakage first
Machine translation often translates the **inside** of ICU placeholders
(argument names, the `plural`/`select` keywords, the selector keywords
`one`/`other`/`few`/`many`, even commas/braces), e.g.
`{count, plural, one {# course} other {# courses}}` becoming
`{数え方、複数形、...}`. react-intl cannot parse these.

For every key the scan flags, rebuild valid ICU: keep the English **skeleton**
(arg names + keywords + braces) and translate only the human-readable text and
the submessage text inside each `{# ...}`. Plural categories: mirror English
`one`/`other`; for Russian add `few`/`many`; CJK (ja/ko/zh/my) may collapse to
`other` only. The submessage text (e.g. `# course`) IS translated; the structure
is not.

### 3. Meaning review — one subagent per language (parallel)
Launch one `general-purpose` agent per language in a single message so they run
concurrently. Point each at its `/tmp/trev/<lang>.json` and have it write
`/tmp/trev/<lang>.fixes.json` = `{"app::key": {"new": "...", "reason": "..."}}`.

Give each agent the native-translator instructions:
- These are UI strings (buttons, tabs, table headers, dialogs, help/toast text).
- Flag ONLY real errors: wrong meaning; wrong grammatical form for a UI label
  (e.g. a conjugated verb where the conventional UI noun/imperative is expected —
  "Save" must not become "he saves"); reversed/garbled compound ("Search team" →
  "the search team"); singular/plural mismatch; left untranslated; inconsistent
  terminology; wrong/over-familiar pronoun register ("You"); wrong word-sense
  (points→opinions, streak→stripe, unit→device, export→trade, assignments→homework).
- Do NOT flag subjective style where the translation is already correct/natural.
- CRITICAL: never alter ICU placeholder argument names, `plural`/`select`
  keywords, selector keywords, or braces — only the human-readable text.

Recurring machine-translation bug patterns to look for: single-word imperatives
conjugated as verbs; "Search/Link X" reversed; dropped words ("Move **up**",
"Remove **course**"); missing progress-state suffixes ("Saving"/"Generating");
untranslated English or markup tags leaking through.

### 4. Apply + validate
```
python3 .claude/skills/translation-review/trans_review.py apply --in /tmp/trev
```
This applies every `*.fixes.json`, rewrites files sorted/UTF-8/indent-2 to match
repo format, then re-runs validation. It must report `JSON invalid: 0 | ICU
errors: 0`. If not, fix the offending keys and re-run `validate`.

### 5. Commit
Stage the changed translation files and commit. Summarize languages touched and
fix counts in the body. Match the repo's existing translation-commit style.

```
git add translations/
git commit
```

Default commit subject: `Review and fix machine-translated strings`.

## Notes
- Validate any time with:
  `python3 .claude/skills/translation-review/trans_review.py validate`
- This skill reviews translation **output**. The translation **pipeline** lives
  in a separate repo (blendxlanggen); harden ICU protection there to stop
  breakage at the source rather than only fixing output.
- Scale the number of review agents to the languages present; if only a few keys
  changed, a single combined review pass is fine instead of full fan-out.
