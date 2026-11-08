"""Helpers shared by the local-LLM tools (llm_review_pass.py, the llm_fix_*.py passes,
check_self_standing.py, check_english_grammar.py) and propose_term_ledger.py, so a fix to
one of them (BOM handling, a crash on a list-valued model answer, a validator that was never
really run, a truncated state file) is made once instead of in every copy.

Nothing here talks to anything but LM Studio's local server (http://127.0.0.1:1234) and the
local validator script: no data leaves the machine.
"""
import hashlib
import json
import os
import re
# runs the trusted validator only: fixed argument list, never a shell
import subprocess  # nosec B404
import sys
import time
import urllib.request

from csv_io import read_dict_csv, write_dict_csv  # noqa: F401  (re-exported for the llm tools)

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-e4b"
MAX_PROMPT_WORDS = 10
MAX_OPTION_WORDS = 3
# Stop a run after this many LLM calls in a row failed (each one already retried): with LM
# Studio down, every remaining batch would otherwise burn its retries and timeout for hours.
MAX_CONSECUTIVE_FAILURES = 3

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
# The validator the fix passes run after rewriting cards. Never the copy inside the course being
# edited: a cloned or contributed course repo could ship any script under that name. Default is
# the owner's python-basics checkout (the reference copy CI also uses); override with
# YAADDI_VALIDATOR=<path to a validate_course.py you trust>.
TRUSTED_VALIDATOR = os.environ.get("YAADDI_VALIDATOR") or os.path.join(REPO_ROOT, "python-basics", "validate_course.py")

# Card types whose options are plain parallel answer choices: the distractors may be reworded,
# but the correct option(s) must stay exactly as they were, at the same position.
OPTION_REWRITE_TYPES = {"multiple_choice", "multi_select", "select_blank", "media_card"}
# Card types whose prompt may be reworded. Every other type (cloze_passage, reading_passage,
# spot_error, code_fill, command_output, image_occlusion, preview_card, ...) keeps its text: the
# prompt there is the passage/code/error being graded, not just a question.
PROMPT_REWRITE_TYPES = OPTION_REWRITE_TYPES | {
    "true_false", "type_answer", "short_answer", "numeric_answer", "image_choice", "order",
    "match_pairs", "categorize", "listening_card",
}

REVIEW_FLAGS = ("forward_references", "missing_or_generic_explanation", "robotic_phrasing", "repetitive_practice")


def read_csv(path):
    """(fieldnames, rows); BOM-safe, raises on a malformed row (see csv_io.read_dict_csv)."""
    return read_dict_csv(path, strict=True)


def find_all_course_dirs(root=REPO_ROOT):
    """Every course folder (one with a meta.json) directly under `root` - by default the repo
    root, whatever the current directory is (running from tools/ used to find 0 courses)."""
    return [
        os.path.join(root, entry)
        for entry in sorted(os.listdir(root))
        if os.path.isdir(os.path.join(root, entry)) and os.path.isfile(os.path.join(root, entry, "meta.json"))
    ]


def call_llm(model, system_prompt, user_content, temperature=0.1, max_tokens=2000, retries=3, timeout=180):
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(LM_STUDIO_URL, data=payload, headers={"Content-Type": "application/json"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # URL is a fixed constant / operator config, not user input
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - bulk unattended run, log & retry
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LM Studio call failed after {retries} attempts: {last_err}")


class LlmFailures:
    """Counts LLM calls that failed in a row; `failed()` returns True once the run should stop."""

    def __init__(self, limit=MAX_CONSECUTIVE_FAILURES):
        self.limit = limit
        self.count = 0
        self.tripped = False

    def ok(self):
        self.count = 0

    def failed(self):
        self.count += 1
        if self.count >= self.limit:
            self.tripped = True
            print(f"    {self.count} LLM calls in a row failed - is LM Studio running at {LM_STUDIO_URL}? Stopping.")
        return self.tripped


def extract_json_array(text):
    """The model's JSON array, tolerating stray text around it, a markdown code fence, and a
    bare object for a one-card batch; None when nothing parses."""
    text = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if text.startswith("[") or text.startswith("{"):
        try:
            value = json.loads(text)
            return [value] if isinstance(value, dict) else value
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return [json.loads(match.group(0))]
        except json.JSONDecodeError:
            return None
    return None


def coerce_str(value, sep=" "):
    """A model field as a stripped string (a JSON list is joined with `sep`), or None when absent."""
    if value is None:
        return None
    if isinstance(value, list):
        value = sep.join(str(x) for x in value)
    return str(value).strip()


def _norm(text):
    return " ".join((text or "").split()).casefold()


def correct_positions(card):
    return [int(x) for x in re.split(r"[|,]", card.get("correct_index") or "") if x.strip().isdigit()]


def rewrite_problem(card, new_prompt=None, new_options=None):
    """None when replacing the card's prompt/options with these values is safe, else the reason.
    None or "" for a field means "unchanged". The grading-relevant parts must survive: options
    of a non-choice type (accepted answer, chip order, pairs, listening select/type prefix) are
    never rewritten, and for a choice type the correct option(s) keep their text and position."""
    ctype = card.get("type") or "multiple_choice"
    orig_prompt = card.get("prompt") or ""
    orig_options = card.get("options") or ""
    prompt_changed = bool(new_prompt) and new_prompt != orig_prompt
    options_changed = bool(new_options) and new_options != orig_options
    if (prompt_changed or options_changed) and ctype not in PROMPT_REWRITE_TYPES:
        return f"{ctype} cards are never rewritten"
    if prompt_changed:
        if len(new_prompt.split()) > MAX_PROMPT_WORDS:
            return "prompt over the word limit"
        if "___" in orig_prompt and "___" not in new_prompt:
            return "prompt lost its ___ blank"
    if options_changed:
        if ctype not in OPTION_REWRITE_TYPES:
            return f"the options of a {ctype} card are its answer and are never rewritten"
        orig = orig_options.split("|")
        new = new_options.split("|")
        if len(new) != len(orig):
            return "option count changed"
        if any(len(o.split(":", 1)[-1].split()) > MAX_OPTION_WORDS for o in new):
            return "an option is over the word limit"
        for i in correct_positions(card):
            if i >= len(orig) or _norm(new[i]) != _norm(orig[i]):
                return "the correct option changed"
    return None


def run_validate(course_dir, validator=None):
    """Card ids the trusted validate_course.py reports an [ERROR] for, or None when the course
    could not be validated (validator missing, crashed, or failed without naming a card): the
    caller must then revert every card it touched instead of keeping them as "validated".
    Runs with -I (no cwd/script-dir imports, no PYTHON* env) on an absolute course path."""
    script = os.path.abspath(validator or TRUSTED_VALIDATOR)
    if not os.path.isfile(script):
        print(f"    ERROR: trusted validator not found at {script} (set YAADDI_VALIDATOR) - edits will be reverted")
        return None
    result = subprocess.run(  # nosec B603
        [sys.executable, "-I", script, os.path.abspath(course_dir), "--source"],
        cwd=os.path.dirname(script), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    bad_ids = set()
    for line in result.stdout.splitlines():
        m = re.search(r"card (\d+)", line)
        if "[ERROR]" in line and m:
            bad_ids.add(m.group(1))
    if result.returncode not in (0, 1) or (result.returncode == 1 and not bad_ids):
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["(no output)"]
        print(f"    ERROR: validator exited {result.returncode} without naming a card: {tail[0][:200]} - edits will be reverted")
        return None
    return bad_ids


def save_json(path, data):
    """Write JSON atomically (temp file + os.replace): a kill mid-write never truncates it."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_json(path, default):
    """The JSON in `path`, or `default` when it is missing. A corrupt (e.g. truncated) file is
    moved aside to <path>.corrupt with a warning instead of crashing the run."""
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        backup = path + ".corrupt"
        os.replace(path, backup)
        print(f"  WARNING: {path} was unreadable ({e}); moved it to {backup} and starting fresh")
        return default


def _hash(parts):
    return hashlib.sha1("\x1f".join(parts).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def question_hash(card):
    return _hash([card.get(f) or "" for f in ("type", "prompt", "options", "correct_index")])


def explanation_hash(card):
    return _hash([card.get("explanation") or ""])


def review_entry_current(entry, card, parts=("question", "explanation")):
    """Whether a llm_review_report.json entry still describes the card as it is now (it was not
    edited since it was reviewed). `parts` picks which hashes matter: a fix pass for the
    explanation does not make a phrasing flag stale. Entries written before hashes existed are
    compared by the 100-character prompt they stored."""
    if "question_hash" not in entry:
        return entry.get("prompt", "") == (card.get("prompt") or "")[:100]
    if "question" in parts and entry.get("question_hash") != question_hash(card):
        return False
    if "explanation" in parts and entry.get("explanation_hash") != explanation_hash(card):
        return False
    return True
