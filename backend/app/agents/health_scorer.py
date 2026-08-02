"""Health Scorer.

Computes the dashboard's repository health metrics with transparent,
documented formulas -- no placeholder numbers. Every score is 0-100 where
higher is healthier, except `technical_debt_index` where higher means MORE
debt (industry convention, e.g. SonarQube's debt ratio).

"Performance Score" from the original vision doc is intentionally not
computed here: it needs runtime profiling data a static scan can't produce,
so it's surfaced by the API as `not_available` rather than faked.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from radon.complexity import cc_visit

from app.agents.architecture_agent import ArchitectureReport
from app.agents.ast_parser.base import ParsedFile
from app.agents.scanner_agent import RepositoryOverview

_TEST_FILE_RE = re.compile(r"(^|[/\\])(test_[\w]+|[\w]+_test|[\w]+\.(test|spec))\.\w+$", re.IGNORECASE)
_TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs"}

_TEXT_SCAN_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".yml", ".yaml", ".json", ".env",
}

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic hardcoded password", re.compile(r"(?i)\bpassword\s*=\s*['\"][^'\"\s]{4,}['\"]")),
    ("Generic hardcoded secret/API key", re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]")),
    ("Private key block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
]

_MAX_SECRET_SCAN_FILES = 3000
_MAX_SECRET_SCAN_BYTES = 300_000


@dataclass
class HealthScores:
    architecture_score: float = 0.0
    documentation_score: float = 0.0
    complexity_score: float = 0.0
    test_coverage_estimated: float = 0.0
    dependency_health_score: float = 100.0
    security_score_basic: float = 100.0
    technical_debt_index: float = 0.0
    notes: dict[str, list[str]] = field(default_factory=dict)
    security_findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "architecture_score": self.architecture_score,
            "documentation_score": self.documentation_score,
            "complexity_score": self.complexity_score,
            "test_coverage_estimated": self.test_coverage_estimated,
            "dependency_health_score": self.dependency_health_score,
            "security_score_basic": self.security_score_basic,
            "technical_debt_index": self.technical_debt_index,
            "performance_score": None,  # requires runtime profiling -- not available from a static scan
            "notes": self.notes,
            "security_findings": self.security_findings,
        }


def _documentation_score(parsed_files: list[ParsedFile]) -> tuple[float, list[str]]:
    total = 0
    documented = 0
    for pf in parsed_files:
        if pf.error:
            continue
        for cls in pf.classes:
            total += 1
            documented += 1 if cls.docstring else 0
            for method in cls.methods:
                total += 1
                documented += 1 if method.docstring else 0
        for func in pf.functions:
            total += 1
            documented += 1 if func.docstring else 0

    if total == 0:
        return 100.0, ["No parsed classes/functions to check documentation on"]
    score = round((documented / total) * 100, 1)
    return score, [f"{documented}/{total} classes & functions have docstrings"]


def _python_complexity(source_dir: Path, parsed_files: list[ParsedFile]) -> list[int]:
    values: list[int] = []
    for pf in parsed_files:
        if pf.language != "Python" or pf.error:
            continue
        try:
            source = (source_dir / pf.path).read_text(encoding="utf-8", errors="ignore")
            blocks = cc_visit(source)
            values.extend(b.complexity for b in blocks)
        except (SyntaxError, ValueError, RecursionError, OSError):
            continue
    return values


def _jsts_complexity_proxy(parsed_files: list[ParsedFile]) -> list[int]:
    """No CC tool for JS/TS in this phase; approximate with function length as a proxy."""
    values: list[int] = []
    for pf in parsed_files:
        if pf.language not in ("JavaScript", "TypeScript") or pf.error:
            continue
        for func in pf.functions:
            values.append(1 + max(0, func.end_line - func.line) // 10)
        for cls in pf.classes:
            for method in cls.methods:
                values.append(1 + max(0, method.end_line - method.line) // 10)
    return values


def _complexity_score(source_dir: Path, parsed_files: list[ParsedFile]) -> tuple[float, list[str]]:
    py_values = _python_complexity(source_dir, parsed_files)
    js_values = _jsts_complexity_proxy(parsed_files)
    all_values = py_values + js_values

    if not all_values:
        return 100.0, ["No functions available to measure complexity on"]

    avg_cc = sum(all_values) / len(all_values)
    score = max(0.0, min(100.0, 100 - (avg_cc - 1) * 10))
    notes = [f"Average cyclomatic complexity ~{round(avg_cc, 1)} across {len(all_values)} functions"]
    if js_values:
        notes.append("JS/TS complexity is a length-based proxy (no CC tool wired up yet), Python uses radon's real McCabe complexity")
    return round(score, 1), notes


def _test_coverage_estimated(overview: RepositoryOverview) -> tuple[float, list[str]]:
    test_files = 0
    source_files = 0
    for rel_path, _lang in overview.parseable_files:
        parts = [p.lower() for p in rel_path.split("/")]
        if _TEST_FILE_RE.search(rel_path) or any(p in _TEST_DIR_NAMES for p in parts):
            test_files += 1
        else:
            source_files += 1

    if source_files == 0:
        return 0.0, ["No source files to compare test files against"]

    ratio = test_files / max(1, source_files)
    score = round(min(100.0, (ratio / 0.5) * 100), 1)
    notes = [
        f"{test_files} test files vs {source_files} source files (ratio {round(ratio, 2)})",
        "This is an estimate from file naming/location, not measured coverage from running tests",
    ]
    return score, notes


def _dependency_health(source_dir: Path, overview: RepositoryOverview) -> tuple[float, list[str]]:
    score = 100.0
    notes: list[str] = []

    if "npm" in overview.package_managers:
        lockfiles = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
        if not any((source_dir / lf).exists() for lf in lockfiles):
            score -= 25
            notes.append("No npm lockfile found (package-lock.json / yarn.lock / pnpm-lock.yaml)")

    if "pip" in overview.package_managers:
        req = source_dir / "requirements.txt"
        if req.exists():
            lines = [
                line.strip()
                for line in req.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            unpinned = [line for line in lines if "==" not in line]
            if lines and len(unpinned) / len(lines) > 0.3:
                score -= 20
                notes.append(f"{len(unpinned)}/{len(lines)} Python dependencies are unpinned (no == version)")

    if not overview.package_managers:
        notes.append("No recognized package manager manifest found")

    if not notes:
        notes.append("Lockfile / version pinning looks healthy")

    return max(0.0, score), notes


def _security_scan(source_dir: Path, overview: RepositoryOverview) -> tuple[float, list[str], list[dict]]:
    findings: list[dict] = []
    notes: list[str] = []
    scanned = 0

    for rel_path, _lang in overview.parseable_files:
        if scanned >= _MAX_SECRET_SCAN_FILES:
            break
        path = source_dir / rel_path
        if path.suffix.lower() not in _TEXT_SCAN_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:_MAX_SECRET_SCAN_BYTES]
        except OSError:
            continue
        scanned += 1

        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule_name, pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append({"file": rel_path, "line": line_no, "rule": rule_name})

    if overview.env_files:
        notes.append(f"{len(overview.env_files)} .env file(s) detected in the repo (values not read)")

    score = max(0.0, 100 - min(80, len(findings) * 10))
    if findings:
        notes.append(f"{len(findings)} potential hardcoded secret pattern(s) found -- basic regex scan, verify manually")
    else:
        notes.append("No hardcoded-secret patterns matched by the basic scan")

    return score, notes, findings[:50]


def _architecture_score(architecture: ArchitectureReport, graph_stats: dict) -> tuple[float, list[str]]:
    if architecture.primary_confidence == 0:
        base = 50.0
        notes = ["No strong architecture pattern signal -- neutral score"]
    else:
        base = architecture.primary_confidence * 100
        notes = [architecture.summary]

    most_coupled = graph_stats.get("most_coupled", [])
    if most_coupled and most_coupled[0]["out_degree"] > 30:
        base -= 10
        notes.append(f"High coupling detected: '{most_coupled[0]['id']}' has {most_coupled[0]['out_degree']} outgoing dependencies")

    return round(max(0.0, min(100.0, base)), 1), notes


def compute_health_scores(
    source_dir: Path,
    overview: RepositoryOverview,
    parsed_files: list[ParsedFile],
    architecture: ArchitectureReport,
    graph_stats: dict,
) -> HealthScores:
    scores = HealthScores()

    scores.documentation_score, scores.notes["documentation"] = _documentation_score(parsed_files)
    scores.complexity_score, scores.notes["complexity"] = _complexity_score(source_dir, parsed_files)
    scores.test_coverage_estimated, scores.notes["test_coverage"] = _test_coverage_estimated(overview)
    scores.dependency_health_score, scores.notes["dependency_health"] = _dependency_health(source_dir, overview)
    scores.security_score_basic, scores.notes["security"], scores.security_findings = _security_scan(source_dir, overview)
    scores.architecture_score, scores.notes["architecture"] = _architecture_score(architecture, graph_stats)

    contributing = [
        scores.documentation_score,
        scores.complexity_score,
        scores.test_coverage_estimated,
        scores.dependency_health_score,
        scores.security_score_basic,
        scores.architecture_score,
    ]
    avg_health = sum(contributing) / len(contributing)
    scores.technical_debt_index = round(100 - avg_health, 1)
    scores.notes["technical_debt"] = [
        "Composite of documentation, complexity, test coverage estimate, dependency health, "
        "basic security scan and architecture score (Performance Score excluded -- not measurable statically)"
    ]

    return scores


def generate_recommendations(scores: HealthScores) -> list[str]:
    recs: list[str] = []
    if scores.documentation_score < 60:
        recs.append(f"Documentation coverage is low ({scores.documentation_score}%) -- add docstrings to public classes and functions.")
    if scores.complexity_score < 60:
        recs.append(f"Several functions look highly complex (score {scores.complexity_score}) -- consider breaking them into smaller units.")
    if scores.test_coverage_estimated < 40:
        recs.append(f"Estimated test coverage is low ({scores.test_coverage_estimated}%) -- add unit tests, especially for core modules.")
    if scores.dependency_health_score < 80:
        recs.append("Dependency hygiene needs attention -- " + "; ".join(scores.notes.get("dependency_health", [])))
    if scores.security_findings:
        recs.append(f"{len(scores.security_findings)} potential hardcoded secret pattern(s) found -- review and move them to environment variables/secret storage.")
    if scores.architecture_score < 50:
        recs.append("Architecture pattern signal is weak or coupling is high -- consider documenting/enforcing a clear layering convention.")
    if not recs:
        recs.append("No major issues detected by the current checks -- nice work.")
    return recs
