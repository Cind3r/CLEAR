# validator.py
import json, re, os, shutil, datetime, itertools, math
from typing import Dict, List, Tuple

WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-\+/]+")
ALT_GROUP = re.compile(r"\(\?:([^()]*)\)")         # capture inside first (?: ... )
PIPE_SPLIT = re.compile(r"(?<!\\)\|")              # split on unescaped |
PLAUSIBLE_CODE = re.compile(
    r"^(?:"
    r"[0-9]{5}"                # CPT 5-digit (e.g., 88305)
    r"|[0-9]{4}[A-Z]"          # CPT with trailing alpha (rare)
    r"|[A-Z]\d{4}"             # HCPCS single letter + 4 digits (J1234, G0008, Q9967, C9290)
    r"|[A-Z]{2}\d{3,4}[A-Z]?"  # HCPCS 2 letters + digits formats
    r")$",
    re.IGNORECASE
)

def _read_rows(mixed_json):  # -> List[Dict[str, str]]
    """Accepts list[dict] or dict[str, list[dict]]. Returns flat [{code, description}]."""
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

def _read_json_any(path: str) -> List[Dict[str, str]]:
    """Reads standard JSON (list/dict) or NDJSON/JSONL (1 object per line)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return _read_rows(obj)
    except json.JSONDecodeError:
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    code = str(item.get("code", "")).strip()
                    desc = str(item.get("description", "")).strip()
                    if code and desc:
                        rows.append({"code": code, "description": desc})
        return rows

def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in WORD.findall(text or "")]

def _tokens_from_pattern(pat: str) -> List[str]:
    no_meta = re.sub(r"[\\^$.?+*{}\[\]()]"," ", pat or "")
    no_boundary = no_meta.replace(r"\b", " ")
    no_spaceclass = no_boundary.replace(r"\s", " ")
    no_pluses = re.sub(r"\s+", " ", no_spaceclass)
    return _tokenize(no_pluses)

def _alt_sort_key(tok: str) -> str:
    """Sort key for an alternation token: strip \b and backslashes, lowercase."""
    t = tok
    t = t.replace(r"\b", "")
    t = t.replace("\\", "")
    return t.strip().lower()

def _join_sorted_alternation(tokens: List[str]) -> str:
    # Remove empties, dedupe while preserving original token content
    toks = [t for t in (tok.strip() for tok in tokens) if t]
    # Dedupe by normalized sort key
    seen = {}
    for t in toks:
        k = _alt_sort_key(t)
        if k not in seen:
            seen[k] = t
    toks_unique = list(seen.values())
    toks_sorted = sorted(toks_unique, key=_alt_sort_key)
    return "|".join(toks_sorted)

def _code_alt_insert(pattern: str, code: str) -> str:
    """
    Insert word-bounded code into the top-level (?: ... ) alternation in ALPHABETICAL order.
    Creates the group if missing. No inline (?i); matching uses IGNORECASE at compile time.
    """
    code_piece = rf"\b{re.escape(code)}\b"
    # If already matched by pattern (case-insensitive), skip
    try:
        if re.search(code_piece, pattern or "", flags=re.IGNORECASE):
            return pattern or ""
    except re.error:
        pass

    m = ALT_GROUP.search(pattern or "")
    if m:
        inner = m.group(1)
        parts = PIPE_SPLIT.split(inner) if inner else []
        parts.append(code_piece)
        new_inner = _join_sorted_alternation(parts)
        start, end = m.span(1)
        return (pattern or "")[:start] + new_inner + (pattern or "")[end:]
    else:
        # Wrap existing pattern and code into a new sorted alternation
        core = pattern or ""
        if core:
            parts = [core, code_piece]
            new_inner = _join_sorted_alternation(parts)
            return f"(?:{new_inner})"
        else:
            return f"(?:{code_piece})"

def _score_match(bundle_name: str, notes: str, pattern: str, desc: str) -> float:
    desc_tokens = set(_tokenize(desc))
    base_tokens = set(_tokenize(bundle_name)) | set(_tokenize(notes)) | set(_tokens_from_pattern(pattern))
    if not desc_tokens or not base_tokens:
        return 0.0
    overlap = len(desc_tokens & base_tokens)
    return overlap / (math.log(2 + len(base_tokens)) + math.log(2 + len(desc_tokens)))

def _ensure_backup(path: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.bak.{ts}"
    shutil.copy2(path, backup)
    return backup

def _sorted_dict(d: Dict[str, dict]) -> Dict[str, dict]:
    """Return a new dict with keys sorted A→Z (case-insensitive)."""
    return dict(sorted(d.items(), key=lambda kv: kv[0].lower()))

def ValidateJSON(
    json_path: str,
    service_config_path: str = "lib/service_config.json",
    dry_run: bool = False,
    verbose: bool = True,
) -> None:
    """
    Validate rows in `json_path` against regex bundles in `service_config_path`.
    Learns plausible codes into best-fit bundles, keeping:
      - No inline (?i) in patterns (HTML/JS safe)
      - Alphabetical ordering of service_config keys
      - Alphabetical ordering inside top-level pattern alternations
    """
    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"Data file not found: {json_path}")
    if not os.path.isfile(service_config_path):
        raise FileNotFoundError(f"service_config.json not found at: {service_config_path}")

    rows = _read_json_any(json_path)

    with open(service_config_path, "r", encoding="utf-8") as f:
        service_config = json.load(f)  # name -> {"pattern","notes"}

    # Pre-compile bundles (Python handles case-insensitive)
    compiled = []
    for name, obj in service_config.items():
        pat = obj.get("pattern", "") or ""
        notes = obj.get("notes", "") or ""
        try:
            cre = re.compile(pat, flags=re.IGNORECASE)
        except re.error:
            cre = None
        compiled.append((name, pat, notes, cre))

    total = len(rows)
    matched = 0
    misses: List[Tuple[str, str]] = []

    for r in rows:
        code, desc = r["code"], r["description"]
        hit = False
        for _, _, _, cre in compiled:
            if cre is None:
                continue
            if cre.search(code) or cre.search(desc):
                hit = True
                break
        if hit:
            matched += 1
        else:
            misses.append((code, desc))

    updates: Dict[str, str] = {}
    auto_bucket_name = "Auto – Needs Review"
    data_issues: List[str] = []

    for code, desc in misses:
        # Covered by existing J-catch-all?
        if re.fullmatch(r"J\d{4}", code, flags=re.IGNORECASE) and any(n.lower().startswith("any j") for n in service_config.keys()):
            matched += 1
            continue

        # Only learn plausible codes
        if not PLAUSIBLE_CODE.match(code):
            data_issues.append(code)
            continue

        # Score best bundle
        scores = []
        for name, pat, notes, cre in compiled:
            s = _score_match(name, notes, pat, desc)
            if cre is not None and cre.search(desc):
                s += 0.25
            scores.append((s, name, pat))
        scores.sort(reverse=True)

        placed = False
        if scores and scores[0][0] >= 0.35:
            _, best_name, best_pat = scores[0]
            new_pat = _code_alt_insert(best_pat, code)
            if new_pat != best_pat:
                updates[best_name] = new_pat
                placed = True

        if not placed:
            # Create/extend auto bucket (sorted alternation)
            current_pat = service_config.get(auto_bucket_name, {}).get("pattern", "")
            new_pat = _code_alt_insert(current_pat, code)
            updates[auto_bucket_name] = new_pat
            service_config.setdefault(
                auto_bucket_name,
                {"pattern": new_pat, "notes": "Codes auto-collected for later review."}
            )

    # Apply updates (patterns sorted internally)
    if updates:
        for bundle_name, new_pat in updates.items():
            if bundle_name not in service_config:
                service_config[bundle_name] = {"pattern": new_pat, "notes": "Codes auto-collected for later review."}
            else:
                service_config[bundle_name]["pattern"] = new_pat

    # Ensure alphabetical ordering of top-level keys before write
    service_config_sorted = _sorted_dict(service_config)

    updated = bool(updates)
    if updated and not dry_run:
        _ensure_backup(service_config_path)
        with open(service_config_path, "w", encoding="utf-8") as f:
            # sort_keys=True guarantees A→Z order in the file
            json.dump(service_config_sorted, f, indent=2, ensure_ascii=False, sort_keys=True)

    # Notify
    if verbose:
        print(f"Matched {matched} / {total} rows.")
        if updated:
            print(f"service_config.json UPDATED ({len(updates)} bundle(s) changed). Backup saved.")
        else:
            print("service_config.json NOT updated (no misses requiring changes).")
        if data_issues:
            uniq = sorted(set(data_issues), key=lambda s: s.lower())
            print(f"Skipped {len(data_issues)} non-plausible codes (unique {len(uniq)}). Examples: {', '.join(uniq[:10])}")
