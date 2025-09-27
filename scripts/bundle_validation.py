# validator.py
import json, re, os, shutil, datetime, itertools, math
from typing import Dict, List, Tuple, Iterable

WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-\+/]+")
CODE_TOKEN = re.compile(r"\b([A-Z]?\d{4,5}|[A-Z]{1,2}\d{3,4}[A-Z]?)\b")  # CPT/HCPCS-ish
ALT_GROUP = re.compile(r"\(\?:([^()]*)\)")  # crude alternation capture inside (?: ... )
PIPE_SPLIT = re.compile(r"(?<!\\)\|")

def _read_rows(mixed_json): # -> List[Dict[str, str]]:
    """
    Accepts list[dict] or dict[str, list[dict]] (like your example).
    Returns a flat list of {code, description}.
    """
    rows = []
    if isinstance(mixed_json, dict):
        iterables = itertools.chain.from_iterable(mixed_json.values())
    elif isinstance(mixed_json, list):
        iterables = mixed_json
    else:
        raise ValueError("Unsupported JSON shape; expected list or dict of lists")

    for it in iterables:
        if not isinstance(it, dict):
            continue
        code = str(it.get("code", "")).strip()
        desc = str(it.get("description", "")).strip()
        if code and desc:
            rows.append({"code": code, "description": desc})
    return rows

def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in WORD.findall(text or "")]

def _tokens_from_pattern(pat: str): # -> List[str]:
    # Pull crude plain-word tokens from a regex to help scoring
    # (we ignore \b, groups, and most metacharacters)
    no_meta = re.sub(r"[\\^$.?+*{}\[\]()]"," ", pat or "")
    no_boundary = no_meta.replace(r"\b", " ")
    no_spaceclass = no_boundary.replace(r"\s", " ")
    # collapse +
    no_pluses = re.sub(r"\s+", " ", no_spaceclass)
    return _tokenize(no_pluses)

def _code_alt_insert(pattern: str, code: str): # -> str:
    """
    Insert an exact word-bounded code into the top-level alternation of `pattern`.
    We look for the first (?: ... ) group; if present, append. Otherwise, create one.
    """
    code_esc = re.escape(code)
    code_piece = rf"\b{code_esc}\b"
    # If pattern already explicitly matches this code, skip
    if re.search(rf"(?i){code_piece}", f"{pattern}"):
        return pattern

    # Find first non-capturing group to extend
    m = ALT_GROUP.search(pattern)
    if m:
        inner = m.group(1)
        new_inner = inner + "|" + code_piece
        start, end = m.span(1)
        return pattern[:start] + new_inner + pattern[end:]
    # Otherwise wrap whole pattern into an alternation with the new code
    core = pattern
    if core.startswith("(?i)"):
        return "(?i)(?:" + core[4:] + "|" + code_piece + ")"
    return "(?i)(?:" + core + "|" + code_piece + ")"

def _score_match(bundle_name: str, notes: str, pattern: str, desc: str): # -> float:
    """
    Simple token overlap score between row description and bundle metadata.
    """
    desc_tokens = set(_tokenize(desc))
    base_tokens = set(_tokenize(bundle_name)) | set(_tokenize(notes)) | set(_tokens_from_pattern(pattern))
    if not desc_tokens or not base_tokens:
        return 0.0
    overlap = len(desc_tokens & base_tokens)
    # normalize by log sizes to avoid bias; add tiny eps
    return overlap / (math.log(2 + len(base_tokens)) + math.log(2 + len(desc_tokens)))

def _ensure_backup(path: str): # -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.bak.{ts}"
    shutil.copy2(path, backup)
    return backup

def ValidateJSON(
    json_path: str,
    service_config_path: str = "../lib/service_config.json",
    dry_run: bool = False,
    verbose: bool = True,
): # -> None:
    """
    Validate rows in `json_path` against regex bundles in `service_config_path`.
    If some rows don't match any bundle, try to add their CODEs into the best-fitting bundle's pattern.
    Falls back to an 'Auto – Needs Review' bundle if no strong fit is found.
    Prints a short summary; returns nothing.
    Set dry_run=True to preview without writing changes.
    """
    # ---- Load inputs
    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"Data file not found: {json_path}")
    if not os.path.isfile(service_config_path):
        raise FileNotFoundError(f"service_config.json not found at: {service_config_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data_in = json.load(f)
    rows = _read_rows(data_in)

    with open(service_config_path, "r", encoding="utf-8") as f:
        service_config = json.load(f)  # name -> {"pattern","notes"}

    # Pre-compile bundle regexes
    compiled = []
    for name, obj in service_config.items():
        pat = obj.get("pattern", "")
        notes = obj.get("notes", "")
        try:
            cre = re.compile(pat, flags=re.IGNORECASE)
        except re.error:
            # If a bad regex sneaks in, skip but keep track
            cre = None
        compiled.append((name, pat, notes, cre))

    total = len(rows)
    matched = 0
    misses: List[Tuple[str, str]] = []  # (code, description) for rows with no match

    for r in rows:
        code, desc = r["code"], r["description"]
        hit = False
        for _, _, _, cre in compiled:
            if cre is None:
                continue
            # a match if either code OR description matches bundle pattern
            if cre.search(code) or cre.search(desc):
                hit = True
                break
        if hit:
            matched += 1
        else:
            misses.append((code, desc))

    # ---- Try to place misses
    updates: Dict[str, str] = {}  # bundle_name -> updated_pattern
    auto_bucket_name = "Auto – Needs Review"

    for code, desc in misses:
        # skip if obviously covered by a generic catch-all like J-codes
        jcode = bool(re.fullmatch(r"J\d{4}", code, flags=re.IGNORECASE))
        if jcode and any(n.lower().startswith("any j") for n in service_config.keys()):
            # Consider this a matched row in spirit; no need to mutate regex
            matched += 1
            continue

        # score best bundle
        scores = []
        for name, pat, notes, cre in compiled:
            s = _score_match(name, notes, pat or "", desc)
            # small bump if the bundle already matches the description (but not code)
            if cre is not None and cre.search(desc):
                s += 0.25
            scores.append((s, name, pat))
        scores.sort(reverse=True)

        placed = False
        if scores and scores[0][0] >= 0.35:  # threshold; tune as needed
            _, best_name, best_pat = scores[0]
            new_pat = _code_alt_insert(best_pat or "(?i)", code)
            if new_pat != best_pat:
                updates[best_name] = new_pat
                placed = True

        if not placed:
            # create or extend the auto bucket with this exact code
            if auto_bucket_name in service_config:
                new_pat = _code_alt_insert(service_config[auto_bucket_name].get("pattern","(?i)"), code)
            else:
                new_pat = rf"(?i)(?:\b{re.escape(code)}\b)"
            updates[auto_bucket_name] = new_pat
            # also ensure notes exist
            service_config.setdefault(auto_bucket_name, {"pattern": new_pat, "notes": "Codes auto-collected for later review."})

    # ---- Apply updates to in-memory config
    if updates:
        for bundle_name, new_pat in updates.items():
            if bundle_name not in service_config:
                service_config[bundle_name] = {"pattern": new_pat, "notes": "Codes auto-collected for later review."}
            else:
                service_config[bundle_name]["pattern"] = new_pat

    # ---- Write back if needed
    updated = bool(updates)
    if updated and not dry_run:
        _ensure_backup(service_config_path)
        with open(service_config_path, "w", encoding="utf-8") as f:
            json.dump(service_config, f, indent=2, ensure_ascii=False)

    # ---- Notify
    if verbose:
        print(f"Matched {matched} / {total} rows.")
        if updated:
            print(f"service_config.json UPDATED ({len(updates)} bundle(s) changed). Backup saved. ")
        else:
            print("service_config.json NOT updated (no misses requiring changes).")

# For direct validation testing
# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 2:
#         print("Usage: python validator.py path/to/file.json [--dry-run]")
#         sys.exit(1)
#     dry = "--dry-run" in sys.argv[2:]
#     validate_and_update(sys.argv[1], service_config_path="lib/service_config.json", dry_run=dry, verbose=True)
