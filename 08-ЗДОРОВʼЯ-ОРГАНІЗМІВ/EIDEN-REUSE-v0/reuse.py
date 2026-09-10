"""Read-only calibration reuse and deliberately selected peer-review packets.

Journal entries stay authoritative for history. A case is a bounded, curated
lesson, not an automatically learned skill or permission to execute its steps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
PROJECT = PACKAGE.parents[2]
SCHEMA = "syntonia_calibration_case_v1"
FIELDS = {
    "schema", "id", "revision", "kind", "status", "title", "tags",
    "applies_when", "not_applicable_when", "principle", "procedure",
    "kill_test", "outcome", "limitations", "cost", "sources", "shareable",
}
TEXT_FIELDS = (
    "title", "applies_when", "not_applicable_when", "principle",
    "kill_test", "outcome", "limitations",
)


class CaseError(ValueError):
    """Invalid case or bounded input."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise CaseError(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_number(value):
    raise CaseError(f"nonfinite number: {value}")


def read_json(path: Path):
    with path.open("rb") as stream:
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise CaseError("case exceeds 256 KiB")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=_reject_number)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CaseError("invalid JSON") from exc


def _text(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 8000


def validate_case(case):
    if not isinstance(case, dict) or set(case) != FIELDS:
        raise CaseError("case fields mismatch")
    if (case["schema"] != SCHEMA or not isinstance(case["id"], str)
            or not re.fullmatch(r"[A-Z0-9_-]{3,80}", case["id"])):
        raise CaseError("invalid schema or id")
    if type(case["revision"]) is not int or case["revision"] < 1:
        raise CaseError("invalid revision")
    if not isinstance(case["kind"], str) or case["kind"] not in {"failure", "recovery", "gain"}:
        raise CaseError("invalid kind")
    if not isinstance(case["status"], str) or case["status"] not in {"candidate", "observed_with_limits", "retired"}:
        raise CaseError("invalid status")
    if type(case["shareable"]) is not bool:
        raise CaseError("shareable must be explicit boolean")
    if not all(_text(case[key]) for key in TEXT_FIELDS):
        raise CaseError("missing context, outcome or limits")
    for key in ("tags", "procedure"):
        if not isinstance(case[key], list) or not 1 <= len(case[key]) <= 32:
            raise CaseError(f"invalid {key}")
        if not all(_text(item) for item in case[key]):
            raise CaseError(f"invalid {key} text")
    cost = case["cost"]
    if not isinstance(cost, dict) or set(cost) != {
        "build_minutes", "attention_minutes_per_day", "api_usd",
        "before_seconds", "after_seconds", "scope", "unknown",
    }:
        raise CaseError("invalid cost fields")
    if not _text(cost["scope"]) or not _text(cost["unknown"]):
        raise CaseError("cost scope and unknowns required")
    for key in ("build_minutes", "attention_minutes_per_day", "api_usd",
                "before_seconds", "after_seconds"):
        value = cost[key]
        if value is not None and (type(value) not in (float, int)
                                  or not math.isfinite(value) or value < 0):
            raise CaseError("cost must be nonnegative or null, not invented zero")
    if not isinstance(case["sources"], list) or not 1 <= len(case["sources"]) <= 8:
        raise CaseError("evidence references required")
    for ref in case["sources"]:
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256", "label"}:
            raise CaseError("invalid source fields")
        if not _text(ref["path"]) or not _text(ref["label"]):
            raise CaseError("invalid source text")
        if not isinstance(ref["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", ref["sha256"]):
            raise CaseError("invalid source digest")
    return case


def check_sources(case, root: Path):
    result = []
    root = root.resolve()
    for ref in case["sources"]:
        relative = Path(ref["path"])
        status = "UNAVAILABLE"
        try:
            path = (root / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(root):
                status = "OUTSIDE_ROOT"
            else:
                with path.open("rb") as stream:
                    raw = stream.read(1048577)
                if len(raw) > 1048576:
                    status = "TOO_LARGE"
                else:
                    status = ("MATCH" if hashlib.sha256(raw).hexdigest() == ref["sha256"]
                              else "CHANGED")
        except (OSError, ValueError):
            status = "UNAVAILABLE"
        result.append({"label": ref["label"], "sha256": ref["sha256"], "status": status})
    return result


def load_cases(directory: Path, root: Path):
    if not directory.is_dir():
        raise CaseError("case directory unavailable")
    cases, issues, seen = [], [], set()
    paths = sorted(directory.glob("*.json"))
    if len(paths) > 4096:
        raise CaseError("too many cases")
    for path in paths:
        try:
            case = validate_case(read_json(path))
            if case["id"] in seen:
                raise CaseError("duplicate case id")
            seen.add(case["id"])
            checked = check_sources(case, root)
            cases.append({"case": case, "evidence": checked,
                          "source_match": all(item["status"] == "MATCH" for item in checked)})
        except (CaseError, OSError) as exc:
            issues.append({"file": path.name, "error": str(exc)})
    return cases, issues


def inventory(entries: Path, cases):
    if not entries.is_dir():
        raise CaseError("journal directory unavailable")
    represented = {Path(ref["path"]).name for item in cases for ref in item["case"]["sources"]}
    paths = sorted(entries.glob("MM_DYNAMIC_CALIBRATION_ENTRY_*.md"))
    return {"journal_count": len(paths), "represented_count": sum(p.name in represented for p in paths),
            "unreviewed": [p.name for p in paths if p.name not in represented],
            "automatic_semantic_extraction": False}


def _terms(text):
    return set(re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE))


def recommend(cases, query: str, limit: int = 3):
    if not query.strip() or len(query) > 8000 or not 1 <= limit <= 20:
        raise CaseError("bounded nonempty query and limit 1..20 required")
    tokens = _terms(query)
    ranked = []
    for item in cases:
        case = item["case"]
        if case["status"] == "retired":
            continue
        tag_terms = _terms(" ".join(case["tags"]))
        other_terms = _terms(" ".join(case[key] for key in TEXT_FIELDS))
        score = len(tokens & tag_terms) * 4 + len(tokens & other_terms)
        if score:
            ranked.append((not item["source_match"], -score, case["id"], {
                "id": case["id"], "kind": case["kind"], "status": case["status"],
                "title": case["title"], "principle": case["principle"],
                "applies_when": case["applies_when"], "not_applicable_when": case["not_applicable_when"],
                "procedure": case["procedure"], "kill_test": case["kill_test"],
                "outcome": case["outcome"], "limitations": case["limitations"], "cost": case["cost"],
                "evidence": item["evidence"], "source_content_matches": item["source_match"],
                "semantic_correctness_verified": False,
                "requires_task_fit_check": True,
            }))
    return [row[3] for row in sorted(ranked, key=lambda row: row[:3])[:limit]]


def peer_packet(cases, issues):
    if issues:
        raise CaseError("resolve invalid or duplicate cases before export")
    selected = [item for item in cases if item["case"]["shareable"]
                and item["case"]["status"] != "retired"]
    if not selected or any(not item["source_match"] for item in selected):
        raise CaseError("export requires selected cases with matching sources")
    public = []
    for item in selected:
        case = item["case"]
        public.append({**{key: value for key, value in case.items()
                          if key not in {"sources", "shareable"}},
                       "source_digests": item["evidence"],
                       "evidence_level": "OWNER_SUMMARY_WITH_LOCAL_CONTENT_MATCH_NOT_PEER_VERIFIED"})
    return {"schema": "syntonia_calibration_peer_packet_v1", "cases": public,
            "review_questions": ["Does the evidence support the bounded claim?",
                                 "Where does this not transfer?",
                                 "What cheaper competent alternative should be tried?",
                                 "Did usable capacity improve after servicing cost?"],
            "automatic_adoption": False, "raw_journal_exported": False}


def read_peer_cases(path: Path):
    packet = read_json(path)
    if not isinstance(packet, dict) or set(packet) != {
        "schema", "cases", "review_questions", "automatic_adoption", "raw_journal_exported"
    }:
        raise CaseError("invalid peer packet fields")
    if (packet["schema"] != "syntonia_calibration_peer_packet_v1"
            or packet["automatic_adoption"] is not False
            or packet["raw_journal_exported"] is not False):
        raise CaseError("invalid peer packet boundary")
    if not isinstance(packet["cases"], list) or not 1 <= len(packet["cases"]) <= 100:
        raise CaseError("invalid peer case count")
    result, seen = [], set()
    public_fields = (FIELDS - {"sources", "shareable"}) | {"source_digests", "evidence_level"}
    for item in packet["cases"]:
        if not isinstance(item, dict) or set(item) != public_fields:
            raise CaseError("invalid peer case fields")
        refs = item["source_digests"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 8:
            raise CaseError("invalid peer evidence")
        if any(not isinstance(ref, dict) or set(ref) != {"label", "sha256", "status"} for ref in refs):
            raise CaseError("invalid peer digest fields")
        case = {key: value for key, value in item.items() if key in FIELDS}
        case["shareable"] = False
        case["sources"] = [{"label": ref["label"], "sha256": ref["sha256"],
                            "path": "__peer_evidence_not_local__"} for ref in refs]
        validate_case(case)
        if case["id"] in seen:
            raise CaseError("duplicate peer case id")
        seen.add(case["id"])
        result.append({"case": case, "source_match": False,
                       "evidence": [{**ref, "status": "PEER_ASSERTION_NOT_VERIFIED"} for ref in refs]})
    return result


def write_packet(path: Path, packet):
    """Publish a derived packet atomically; never edit a calibration journal."""
    payload = (json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > 262144 or path.suffix.lower() != ".json":
        raise CaseError("packet must be a JSON file within 256 KiB")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".reuse-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise CaseError("output exists with different content; use a new version") from None
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "query", "export", "peer-query"))
    parser.add_argument("--root", type=Path, default=PROJECT)
    parser.add_argument("--cases", type=Path, default=PACKAGE / "reuse_cases")
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--packet", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "peer-query":
            if args.packet is None:
                raise CaseError("peer-query requires --packet")
            cases, issues = read_peer_cases(args.packet), []
        else:
            cases, issues = load_cases(args.cases, args.root)
        if args.command == "export":
            result = peer_packet(cases, issues)
            if args.output:
                write_packet(args.output, result)
                result = {"status": "WRITTEN", "path": str(args.output), "case_count": len(result["cases"])}
        elif args.command in {"query", "peer-query"}:
            result = {"matches": recommend(cases, args.query, args.limit), "issues": issues,
                      "retrieval": "LEXICAL_ADVISORY_NOT_SEMANTIC_PROOF", "model_invoked": False}
        else:
            result = {**inventory(args.root / "mylytsi_memory/runtime/dynamic_calibration_journal_v0_1/entries", cases),
                      "case_count": len(cases), "issues": issues, "model_invoked": False}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (CaseError, OSError) as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
