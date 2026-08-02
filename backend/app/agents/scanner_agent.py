"""Repository Scanner Agent.

Walks the entire repository tree once and produces a RepositoryOverview:
languages, frameworks, package managers, Docker/Kubernetes/CI-CD signals,
env/secret file locations (paths only -- values are never read), database
and third-party API hints, and the list of files the AST Parsing Agent
should deep-parse.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.agents.language_detection import DEEP_PARSE_LANGUAGES, IGNORED_DIR_NAMES, detect_language

FRAMEWORK_KEYWORDS = {
    "next": "Next.js",
    "react": "React",
    "@angular/core": "Angular",
    "vue": "Vue.js",
    "svelte": "Svelte",
    "express": "Express.js",
    "@nestjs/core": "NestJS",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring-boot": "Spring Boot",
    "spring-boot-starter": "Spring Boot",
    "laravel/framework": "Laravel",
    "rails": "Ruby on Rails",
}

DATABASE_KEYWORDS = {
    "pg": "PostgreSQL",
    "postgres": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "mongoose": "MongoDB",
    "pymongo": "MongoDB",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "pymysql": "MySQL",
    "mysqlclient": "MySQL",
    "redis": "Redis",
    "ioredis": "Redis",
    "sqlite3": "SQLite",
    "sqlalchemy": "SQL (via SQLAlchemy ORM)",
}

API_KEYWORDS = {
    "stripe": "Stripe",
    "twilio": "Twilio",
    "@sendgrid/mail": "SendGrid",
    "sendgrid": "SendGrid",
    "aws-sdk": "AWS SDK",
    "@aws-sdk": "AWS SDK",
    "boto3": "AWS SDK",
    "@google-cloud": "Google Cloud",
    "google-cloud": "Google Cloud",
    "openai": "OpenAI API",
    "firebase": "Firebase",
    "firebase-admin": "Firebase",
}

ENV_FILE_NAMES = {".env", ".env.local", ".env.development", ".env.production", ".env.staging", ".env.test"}
README_NAMES = {"readme.md", "readme.rst", "readme.txt", "readme"}


@dataclass
class RepositoryOverview:
    total_files: int = 0
    total_dirs: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    frameworks: set[str] = field(default_factory=set)
    package_managers: set[str] = field(default_factory=set)
    databases: set[str] = field(default_factory=set)
    third_party_apis: set[str] = field(default_factory=set)
    has_docker: bool = False
    has_kubernetes: bool = False
    ci_cd: set[str] = field(default_factory=set)
    has_readme: bool = False
    env_files: list[str] = field(default_factory=list)
    migration_dirs: set[str] = field(default_factory=set)
    dependency_count: int = 0
    parseable_files: list[tuple[str, str]] = field(default_factory=list)  # (rel_path, language)

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "languages": self.languages,
            "frameworks": sorted(self.frameworks),
            "package_managers": sorted(self.package_managers),
            "databases": sorted(self.databases),
            "third_party_apis": sorted(self.third_party_apis),
            "has_docker": self.has_docker,
            "has_kubernetes": self.has_kubernetes,
            "ci_cd": sorted(self.ci_cd),
            "has_readme": self.has_readme,
            "env_files": self.env_files,
            "migration_dirs": sorted(self.migration_dirs),
            "dependency_count": self.dependency_count,
        }


def _match_keywords(names: list[str], mapping: dict[str, str]) -> set[str]:
    found = set()
    lowered = [n.lower() for n in names]
    for dep in lowered:
        for keyword, label in mapping.items():
            if keyword in dep:
                found.add(label)
    return found


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _handle_package_json(path: Path, overview: RepositoryOverview) -> None:
    text = _read_text(path)
    overview.package_managers.add("npm")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return
    deps = list(data.get("dependencies", {}).keys()) + list(data.get("devDependencies", {}).keys())
    overview.dependency_count += len(deps)
    overview.frameworks |= _match_keywords(deps, FRAMEWORK_KEYWORDS)
    overview.databases |= _match_keywords(deps, DATABASE_KEYWORDS)
    overview.third_party_apis |= _match_keywords(deps, API_KEYWORDS)


def _handle_requirements_txt(path: Path, overview: RepositoryOverview) -> None:
    text = _read_text(path)
    overview.package_managers.add("pip")
    deps = [
        line.strip().split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0]
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    overview.dependency_count += len(deps)
    overview.frameworks |= _match_keywords(deps, FRAMEWORK_KEYWORDS)
    overview.databases |= _match_keywords(deps, DATABASE_KEYWORDS)
    overview.third_party_apis |= _match_keywords(deps, API_KEYWORDS)


def _handle_pyproject_toml(path: Path, overview: RepositoryOverview) -> None:
    text = _read_text(path)
    overview.package_managers.add("poetry" if "[tool.poetry]" in text else "pip")
    overview.frameworks |= _match_keywords([text], FRAMEWORK_KEYWORDS)
    overview.databases |= _match_keywords([text], DATABASE_KEYWORDS)
    overview.third_party_apis |= _match_keywords([text], API_KEYWORDS)


def _handle_pom_xml(path: Path, overview: RepositoryOverview) -> None:
    overview.package_managers.add("maven")
    text = _read_text(path).lower()
    if "spring-boot" in text:
        overview.frameworks.add("Spring Boot")


def _handle_build_gradle(path: Path, overview: RepositoryOverview) -> None:
    overview.package_managers.add("gradle")
    text = _read_text(path).lower()
    if "spring-boot" in text:
        overview.frameworks.add("Spring Boot")


def _handle_go_mod(path: Path, overview: RepositoryOverview) -> None:
    overview.package_managers.add("go modules")


def _handle_gemfile(path: Path, overview: RepositoryOverview) -> None:
    overview.package_managers.add("bundler")
    text = _read_text(path).lower()
    if "rails" in text:
        overview.frameworks.add("Ruby on Rails")


def _handle_composer_json(path: Path, overview: RepositoryOverview) -> None:
    overview.package_managers.add("composer")
    text = _read_text(path).lower()
    if "laravel/framework" in text:
        overview.frameworks.add("Laravel")


MANIFEST_HANDLERS = {
    "package.json": _handle_package_json,
    "requirements.txt": _handle_requirements_txt,
    "pyproject.toml": _handle_pyproject_toml,
    "pom.xml": _handle_pom_xml,
    "build.gradle": _handle_build_gradle,
    "build.gradle.kts": _handle_build_gradle,
    "go.mod": _handle_go_mod,
    "gemfile": _handle_gemfile,
    "composer.json": _handle_composer_json,
}


def _looks_like_k8s_manifest(text: str) -> bool:
    return "apiVersion:" in text and "kind:" in text


def scan_repository(source_dir: Path) -> RepositoryOverview:
    overview = RepositoryOverview()

    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [
            d for d in dirs
            if d not in IGNORED_DIR_NAMES and (not d.startswith(".") or d == ".github")
        ]
        overview.total_dirs += len(dirs)
        root_path = Path(root)

        for filename in files:
            file_path = root_path / filename
            rel_path = str(file_path.relative_to(source_dir)).replace(os.sep, "/")
            overview.total_files += 1

            language = detect_language(filename)
            if language:
                overview.languages[language] = overview.languages.get(language, 0) + 1
                if language in DEEP_PARSE_LANGUAGES:
                    overview.parseable_files.append((rel_path, language))

            lower_name = filename.lower()

            if lower_name == "dockerfile" or lower_name.endswith(".dockerfile"):
                overview.has_docker = True
            if lower_name in {"docker-compose.yml", "docker-compose.yaml"}:
                overview.has_docker = True

            if rel_path.startswith(".github/workflows/") and lower_name.endswith((".yml", ".yaml")):
                overview.ci_cd.add("GitHub Actions")
            if lower_name == ".gitlab-ci.yml":
                overview.ci_cd.add("GitLab CI")
            if lower_name == "jenkinsfile":
                overview.ci_cd.add("Jenkins")

            if lower_name in README_NAMES:
                overview.has_readme = True

            if lower_name in ENV_FILE_NAMES or (lower_name.startswith(".env.") and lower_name not in ENV_FILE_NAMES):
                overview.env_files.append(rel_path)

            if "migrations" in file_path.parts or "alembic" in file_path.parts:
                overview.migration_dirs.add(str(file_path.parent.relative_to(source_dir)).replace(os.sep, "/"))

            if lower_name.endswith((".yaml", ".yml")) and "workflows" not in file_path.parts:
                text = _read_text(file_path, limit=4000)
                if _looks_like_k8s_manifest(text):
                    overview.has_kubernetes = True

            handler = MANIFEST_HANDLERS.get(lower_name)
            if handler:
                handler(file_path, overview)

    return overview
