"""Architecture Understanding Agent.

Rule-based pattern detection from folder-structure signals and deployable-unit
shape. Every match carries a confidence score and the concrete signals that
produced it -- this is a heuristic, not certainty, and the report says so.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from app.agents.language_detection import IGNORED_DIR_NAMES
from app.agents.scanner_agent import RepositoryOverview

PATTERN_SIGNALS: dict[str, set[str]] = {
    "MVC": {"controllers", "models", "views", "controller", "model", "view"},
    "Layered Architecture": {"service", "services", "repository", "repositories", "dao", "controller", "controllers"},
    "Clean / Hexagonal Architecture": {
        "domain", "application", "infrastructure", "usecases", "use_cases", "ports", "adapters",
    },
    "Domain-Driven Design (DDD)": {
        "domain", "aggregates", "aggregate", "entities", "valueobjects", "value_objects", "bounded_context",
    },
    "CQRS": {"commands", "queries", "handlers", "commandhandlers", "queryhandlers"},
    "Event-Driven Architecture": {
        "events", "kafka", "rabbitmq", "pubsub", "consumers", "producers", "queue", "queues", "subscribers",
    },
}

_SERVERLESS_FILES = {"serverless.yml", "serverless.yaml", "vercel.json", "netlify.toml", "template.yaml", "sam.yaml"}
_SERVICE_MANIFESTS = ("Dockerfile", "package.json", "requirements.txt", "go.mod", "pom.xml")


@dataclass
class ArchitecturePatternMatch:
    pattern: str
    confidence: float
    matched_signals: list[str] = field(default_factory=list)


@dataclass
class ArchitectureReport:
    primary_pattern: str
    primary_confidence: float
    matches: list[ArchitecturePatternMatch]
    is_microservices: bool
    service_count: int
    summary: str

    def to_dict(self) -> dict:
        return {
            "primary_pattern": self.primary_pattern,
            "primary_confidence": self.primary_confidence,
            "matches": [
                {"pattern": m.pattern, "confidence": m.confidence, "matched_signals": m.matched_signals}
                for m in self.matches
            ],
            "is_microservices": self.is_microservices,
            "service_count": self.service_count,
            "summary": self.summary,
        }


def _collect_signals(source_dir: Path) -> tuple[set[str], list[str], bool]:
    dir_names: set[str] = set()
    has_serverless = False

    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIR_NAMES and not d.startswith(".")]
        for d in dirs:
            dir_names.add(d.lower())
        for f in files:
            if f.lower() in _SERVERLESS_FILES:
                has_serverless = True

    service_dirs: list[str] = []
    for entry in source_dir.iterdir():
        if entry.is_dir() and entry.name.lower() not in IGNORED_DIR_NAMES and not entry.name.startswith("."):
            if any((entry / manifest).exists() for manifest in _SERVICE_MANIFESTS):
                service_dirs.append(entry.name)

    return dir_names, service_dirs, has_serverless


def detect_architecture(source_dir: Path, overview: RepositoryOverview) -> ArchitectureReport:
    dir_names, service_dirs, has_serverless = _collect_signals(source_dir)

    matches: list[ArchitecturePatternMatch] = []
    for pattern, signals in PATTERN_SIGNALS.items():
        matched = sorted(signals & dir_names)
        if matched:
            confidence = round(min(1.0, len(matched) / max(2, len(signals) * 0.4)), 2)
            matches.append(ArchitecturePatternMatch(pattern, confidence, matched))

    is_microservices = len(service_dirs) >= 3
    if is_microservices:
        matches.append(
            ArchitecturePatternMatch("Microservices", round(min(1.0, len(service_dirs) / 5), 2), service_dirs)
        )
    elif len(service_dirs) <= 1:
        matches.append(ArchitecturePatternMatch("Monolith", 0.6, ["single deployable unit detected"]))

    if has_serverless:
        matches.append(ArchitecturePatternMatch("Serverless", 0.8, ["serverless/IaC config file found"]))

    matches.sort(key=lambda m: m.confidence, reverse=True)
    primary = matches[0] if matches else ArchitecturePatternMatch("Undetermined", 0.0, [])

    if primary.confidence == 0:
        summary = "Not enough structural signal to confidently classify the architecture pattern."
    else:
        signals_text = ", ".join(primary.matched_signals) if primary.matched_signals else "framework/folder conventions"
        summary = f"Detected {primary.pattern} pattern ({int(primary.confidence * 100)}% confidence) based on: {signals_text}."

    return ArchitectureReport(
        primary_pattern=primary.pattern,
        primary_confidence=primary.confidence,
        matches=matches,
        is_microservices=is_microservices,
        service_count=len(service_dirs),
        summary=summary,
    )
