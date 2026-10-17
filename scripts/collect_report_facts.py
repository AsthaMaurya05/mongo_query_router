"""Collect reproducible, read-only facts for the MongoDB project report."""

from __future__ import annotations

import ast
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "report_facts.md"
DB_NAME = "shop_db"
PACKAGES = ("pymongo", "fastapi", "uvicorn", "groq", "pydantic", "pytest", "faker")


def stringify(value: Any) -> Any:
    """Make BSON and date values JSON serializable without changing values."""
    if isinstance(value, (ObjectId, datetime, date)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): stringify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [stringify(item) for item in value]
    return value


def json_text(value: Any) -> str:
    return json.dumps(stringify(value), indent=2, default=str, ensure_ascii=False)


def command_output(args: list[str], timeout: int = 600) -> str:
    """Return complete command output, including failures, without raising."""
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"NOT FOUND\n{error}"

    output = (result.stdout or "") + (result.stderr or "")
    return f"$ {' '.join(args)}\nexit code: {result.returncode}\n{output.rstrip()}"


def read_file(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.is_file():
        return "NOT FOUND"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        return f"NOT FOUND ({error})"


def fenced(text: str, language: str = "text") -> str:
    return f"```{language}\n{text.rstrip()}\n```"


def folder_tree() -> str:
    excluded = {".git", ".pytest_cache", "__pycache__", "venv"}
    lines: list[str] = []
    paths = sorted(
        path for path in ROOT.rglob("*")
        if not any(part in excluded for part in path.relative_to(ROOT).parts)
    )
    for path in paths:
        relative = path.relative_to(ROOT)
        indent = "  " * (len(relative.parts) - 1)
        suffix = "/" if path.is_dir() else ""
        lines.append(f"{indent}{relative.name}{suffix}")
    return "\n".join(lines) or "NOT FOUND"


def environment_section() -> str:
    try:
        from app.db import client

        mongo_version = client.server_info().get("version", "NOT FOUND")
    except Exception as error:
        mongo_version = f"NOT FOUND ({error})"

    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "NOT FOUND"

    return "\n".join([
        "## 1. ENVIRONMENT",
        "",
        f"- MongoDB server version (`db.version()` equivalent via PyMongo): `{mongo_version}`",
        f"- Python version: `{sys.version.replace(chr(10), ' ')}`",
        f"- Platform: `{platform.platform()}`",
        "",
        "Package versions from the active Python environment:",
        fenced(json_text(versions), "json"),
    ])


def repository_section() -> str:
    return "\n".join([
        "## 2. REPOSITORY",
        "",
        "### GitHub remote URL",
        fenced(command_output(["git", "remote", "-v"]), "text"),
        "",
        "### All commits",
        fenced(command_output(["git", "log", "--oneline"]), "text"),
        "",
        "### Folder tree (excluded: venv, __pycache__, .git, .pytest_cache)",
        fenced(folder_tree(), "text"),
        "",
        "### README full contents",
        fenced(read_file("README"), "markdown"),
        "",
        "### requirements.txt full contents",
        fenced(read_file("requirements.txt"), "text"),
    ])


def database_section() -> str:
    try:
        from app.db import get_db

        db = get_db(DB_NAME)
        collection_names = sorted(db.list_collection_names())
        facts: dict[str, Any] = {
            "database": DB_NAME,
            "collections": {},
            "stats": db.command("collStats", collection_names[0]) if False else {},
        }
        stats = db.command("dbStats")
        facts["stats"] = {
            "dataSize_MB": round(stats.get("dataSize", 0) / 1024 / 1024, 4),
            "storageSize_MB": round(stats.get("storageSize", 0) / 1024 / 1024, 4),
        }
        for name in collection_names:
            collection = db[name]
            indexes = [
                {"name": item["name"], "key": dict(item["key"])}
                for item in collection.list_indexes()
            ]
            options = db.command("listCollections", filter={"name": name})[
                "cursor"
            ]["firstBatch"][0].get("options", {})
            facts["collections"][name] = {
                "document_count": collection.count_documents({}),
                "indexes": indexes,
                "validator": options.get("validator", "NOT FOUND"),
                "sample_document": collection.find_one({}),
            }
        return "\n".join([
            "## 3. DATABASE FACTS",
            "",
            fenced(json_text(facts), "json"),
        ])
    except Exception as error:
        return "\n".join([
            "## 3. DATABASE FACTS",
            "",
            fenced(f"NOT FOUND ({error})", "text"),
        ])


def data_section() -> str:
    try:
        from app.db import get_db

        db = get_db(DB_NAME)
        status_counts = {
            row["_id"]: row["count"]
            for row in db.orders.aggregate([
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ])
        }
        date_row = next(db.orders.aggregate([
            {
                "$group": {
                    "_id": None,
                    "minimum": {"$min": "$created_at"},
                    "maximum": {"$max": "$created_at"},
                }
            }
        ]), {})
        rating_row = next(db.reviews.aggregate([
            {"$group": {"_id": None, "average_rating": {"$avg": "$rating"}}}
        ]), {})
        facts = {
            "orders_count_by_status": status_counts,
            "orders_min_created_at": date_row.get("minimum", "NOT FOUND"),
            "orders_max_created_at": date_row.get("maximum", "NOT FOUND"),
            "reviews_count": db.reviews.count_documents({}),
            "average_rating_overall": rating_row.get("average_rating", "NOT FOUND"),
            "products_with_stock_less_than_10": db.products.count_documents(
                {"stock": {"$lt": 10}}
            ),
        }
        return "\n".join(["## 4. DATA FACTS", "", fenced(json_text(facts), "json")])
    except Exception as error:
        return "\n".join(["## 4. DATA FACTS", "", fenced(f"NOT FOUND ({error})", "text")])


def endpoint_facts() -> str:
    try:
        from app.api.main import app

        routes = []
        for route in app.routes:
            if not hasattr(route, "methods"):
                continue
            endpoint = route.endpoint
            routes.append({
                "methods": sorted(route.methods),
                "path": route.path,
                "request_model": (
                    "QueryRequest" if route.path == "/api/query" else "none"
                ),
                "response_shape": (
                    "object containing pipeline, params, rows, message/answer"
                    if route.path == "/api/query"
                    else (
                        '{"status": "ok", "database": "<API_DB_NAME>"}'
                        if route.path == "/health"
                        else "HTML document"
                    )
                ),
                "http_status_codes": (
                    [200, 422, 503]
                    if route.path == "/api/query"
                    else ([200, 503] if route.path == "/health" else [200])
                ),
            })
        return json_text(routes)
    except Exception as error:
        return f"NOT FOUND ({error})"


def api_section() -> str:
    external_ui = []
    for pattern in ("**/*.html", "**/*.js", "**/*.css"):
        external_ui.extend(
            str(path.relative_to(ROOT))
            for path in ROOT.glob(pattern)
            if not any(part in {".git", "venv", "__pycache__", ".pytest_cache"}
                       for part in path.relative_to(ROOT).parts)
        )
    ui_files = "\n".join(external_ui) if external_ui else "NOT FOUND"
    return "\n".join([
        "## 5. API FACTS",
        "",
        "### app/api/main.py full contents",
        fenced(read_file("app/api/main.py"), "python"),
        "",
        "### Web UI files (HTML, JS, CSS)",
        fenced(ui_files, "text"),
        "",
        "The dashboard UI is embedded in `app/api/main.py` when external UI files are NOT FOUND.",
        "",
        "### Endpoints",
        fenced(endpoint_facts(), "json"),
        "",
        f"API database configuration from source: `{read_api_db_name()}`",
        "",
        "### Seed scripts and database targets",
        "- `seed_demo.py` full contents:",
        fenced(read_file("seed_demo.py"), "python"),
        "- `seed_demo_data.py` full contents:",
        fenced(read_file("seed_demo_data.py"), "python"),
        "Both seed scripts write to the dedicated `mongo_query_router_api_dev` database.",
    ])


def read_api_db_name() -> str:
    source = read_file("app/api/main.py")
    marker = '    "mongo_query_router_api_dev",'
    if marker in source:
        return "mongo_query_router_api_dev (default; API_DB_NAME may override it)"
    return "NOT FOUND"


def ai_section() -> str:
    questions_source = read_file("tests/router_questions.py")
    try:
        tree = ast.parse(questions_source)
        questions = ast.literal_eval(
            next(
                node.value for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                and any(getattr(target, "id", None) == "ROUTER_QUESTIONS"
                        for target in node.targets)
            )
        )
        question_summary = f"Question count: {len(questions)}\nFirst 5:\n{json_text(questions[:5])}"
    except Exception as error:
        question_summary = f"NOT FOUND ({error})"

    model_names = set()
    for source in (read_file("app/ai/router.py"), read_file("app/ai/summarizer.py")):
        for line in source.splitlines():
            if "DEFAULT_MODEL" in line or "GROQ_MODEL" in line:
                model_names.add(line.strip())
    model_names.add(f"Active GROQ_MODEL from environment: {os.getenv('GROQ_MODEL', 'NOT FOUND')}")

    return "\n".join([
        "## 6. AI ROUTER FACTS",
        "",
        "### Model-related source facts",
        fenced("\n".join(sorted(model_names)) or "NOT FOUND", "text"),
        "",
        "### app/ai/router.py",
        fenced(read_file("app/ai/router.py"), "python"),
        "",
        "### app/ai/summarizer.py",
        fenced(read_file("app/ai/summarizer.py"), "python"),
        "",
        "### Other files in app/ai",
        fenced(read_file("app/ai/__init__.py"), "python"),
        "",
        "### Router questions",
        fenced(question_summary, "text"),
        "",
        "### tests/evaluate_router.py",
        fenced(read_file("tests/evaluate_router.py"), "python"),
        "",
        "### Real Groq evaluation output",
        fenced(command_output([
            sys.executable, "-m", "tests.evaluate_router"
        ], 900), "text"),
    ])


def tests_section() -> str:
    return "\n".join([
        "## 7. TEST FACTS",
        "",
        fenced(command_output([sys.executable, "-m", "pytest", "tests", "-v"], 900), "text"),
    ])


def checks_section() -> str:
    return "\n".join([
        "## 8. CHECK SCRIPTS",
        "",
        fenced(command_output([
            sys.executable, "-m", "scripts.check_pipeline_ground_truth"
        ], 900), "text"),
    ])


def examples_section() -> str:
    questions = [
        "Top 5 categories by revenue last month",
        "Who are the top 10 customers this year?",
        "Which products have fewer than 15 units in stock?",
        "Show monthly revenue for 2026",
        "What is the order status breakdown for September 2026?",
        "Which 5 products have the best average rating with at least 10 reviews?",
    ]
    assistant_path = ROOT / "app" / "ai" / "assistant.py"
    if not assistant_path.is_file():
        result = "NOT FOUND: app/ai/assistant.py does not exist; ask() cannot be run."
    else:
        result = "NOT FOUND: assistant.py exists, but its ask() contract was not identifiable safely."
    return "\n".join([
        "## 9. RUN EXAMPLES",
        "",
        fenced("\n".join(f"- {question}" for question in questions), "text"),
        "",
        fenced(result, "text"),
    ])


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sections = [
        "# Mongo Query Router Report Facts",
        "",
        "Generated from the checked-out project and read-only queries/commands.",
        environment_section(),
        repository_section(),
        database_section(),
        data_section(),
        api_section(),
        ai_section(),
        tests_section(),
        checks_section(),
        examples_section(),
    ]
    report = "\n\n".join(sections).rstrip() + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report, end="")


if __name__ == "__main__":
    main()
