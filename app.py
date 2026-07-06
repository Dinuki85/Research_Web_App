"""
CodeRefactor AI — Web Interface
================================
Flask web application for analyzing GitHub repos, detecting code smells,
and refactoring Python functions via OpenRouter API.

Workflow:
  1. User inputs a public GitHub repo URL
  2. App clones the repo and extracts all Python functions
  3. Code smell detection marks each function as good/bad
  4. User selects a function and clicks "Refactor"
  5. System suggests a refactored version via LLM
"""

import os
import re
import sys
import json
import tempfile
import shutil
import traceback
from pathlib import Path

import flask
from flask import Flask, render_template, request, jsonify, session

# Ensure src is on the path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Load .env file if present (for DEFAULT_API_KEY)
from dotenv import load_dotenv
load_dotenv(SCRIPT_DIR / ".env")

from src.repo_analyzer import scan_functions, clone_repository
from src.code_smell_detector import predict_smell_batch, predict_smell
from src.llm_recommender import detect_code_smells, get_best_llm, get_ranking, SMELL_NAMES
from src.refactoring_engine import refactor_function, verify_refactored_code, _clean_code_output
from src.language_detector import is_python_repo, detect_language_by_extensions

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB limit

# ── Helpers ──────────────────────────────────────────────────────────────────

SMELL_LABELS = {
    "long_method": "Long Method",
    "long_param_list": "Long Parameter List",
    "deep_nesting": "Deep Nesting",
    "magic_numbers": "Magic Numbers",
    "no_docstring": "No Docstring",
    "no_type_hints": "No Type Hints & Annotations",
    "long_lines": "Long Lines (>79 chars)",
    "commented_code": "Commented-out Code",
    "poor_naming": "Poor Naming Conventions",
}

def _format_smells(smell_details: dict) -> list:
    """Format smell details for display."""
    result = []
    for smell_key, detected in smell_details.items():
        if detected:
            result.append({
                "key": smell_key,
                "label": SMELL_LABELS.get(smell_key, smell_key.replace("_", " ").title()),
            })
    return result

def _cleanup_temp(temp_dir: str):
    """Safely remove a temporary directory."""
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Landing page — repo URL input."""
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """Clone repo, scan functions, detect smells, and show results."""
    repo_url      = request.form.get("repo_url", "").strip()
    specific_file = request.form.get("specific_file", "").strip()
    if not repo_url:
        return render_template("index.html", error="Please enter a GitHub repository URL.")

    temp_dir = None
    error = None
    functions = []

    try:
        # ── Resolve path or clone ────────────────────────────────────────
        is_remote = repo_url.startswith("http://") or repo_url.startswith("https://") or repo_url.startswith("git@")
        is_local_path = repo_url.startswith("/") or repo_url.startswith("~") or repo_url.startswith(".")

        if is_local_path:
            # Local path — scan directly
            repo_path = Path(repo_url).expanduser().resolve()
            if not repo_path.exists():
                return render_template("index.html", error=f"Path does not exist: {repo_path}")
            if not repo_path.is_dir():
                return render_template("index.html", error="Path is not a directory.")
        elif is_remote:
            # Remote git URL — clone
            temp_dir = tempfile.mkdtemp(prefix="coderefactor-web-")
            repo_path = clone_repository(repo_url, Path(temp_dir))
        else:
            # GitHub shorthand (e.g. "user/repo") — convert to URL and clone
            github_url = f"https://github.com/{repo_url}" if "/" in repo_url else f"https://github.com/{repo_url}/{repo_url}"
            temp_dir = tempfile.mkdtemp(prefix="coderefactor-web-")
            repo_path = clone_repository(github_url, Path(temp_dir))

        # ── Language detection (gate: Python only) ───────────────────────
        # Runs on raw repo files BEFORE scan_functions() — reliable for
        # all repo types including mixed repos.
        ok, detected_lang, confidence = detect_language_by_extensions(repo_path)
        if not ok:
            _cleanup_temp(temp_dir)
            session.pop("temp_dir", None)
            return render_template(
                "index.html",
                error=(
                    f"Detected {detected_lang} repository "
                    f"(confidence: {confidence * 100:.0f}%). "
                    "This tool only supports Python repositories. "
                    "Please submit a Python project."
                ),
                repo_url=repo_url,
                specific_file=specific_file,
            )

        # ── Scan functions ───────────────────────────────────────────────
        all_functions = scan_functions(repo_path)
        if not all_functions:
            return render_template(
                "index.html",
                error="No Python functions found in this repository.",
                repo_url=repo_url,
                specific_file=specific_file,
            )

        # ── Optional: filter to a specific file ──────────────────────────
        if specific_file:
            # Normalise separator so both  src/utils.py  and  src\utils.py  work
            norm_filter = specific_file.replace("\\", "/")
            filtered = [
                f for f in all_functions
                if f.get("rel_path", "").replace("\\", "/").endswith(norm_filter)
            ]
            if not filtered:
                # Check if the path even exists in the repo
                target_path = repo_path / specific_file
                if not target_path.exists():
                    return render_template(
                        "index.html",
                        error=f"File not found in repository: {specific_file}",
                        repo_url=repo_url,
                        specific_file=specific_file,
                    )
                return render_template(
                    "index.html",
                    error=f"No Python functions found in: {specific_file}",
                    repo_url=repo_url,
                    specific_file=specific_file,
                )
            all_functions = filtered

        # ── Detect smells ────────────────────────────────────────────────
        codes = [f["source_code"] for f in all_functions]
        smell_results = predict_smell_batch(codes)

        for i, func in enumerate(all_functions):
            func["is_bad_smell"] = smell_results[i]["is_bad_smell"]
            func["smell_probability"] = smell_results[i]["probability"]
            func["smell_details"] = detect_code_smells(func["source_code"])
            func["display_smells"] = _format_smells(func["smell_details"])
            func["smell_count"] = len(func["display_smells"])
            # Clean source for display
            func["display_code"] = func["source_code"]

        # Sort: bad smells first, then by name
        all_functions.sort(key=lambda f: (not f["is_bad_smell"], f["full_name"]))

        bad_count = sum(1 for f in all_functions if f["is_bad_smell"])
        good_count = len(all_functions) - bad_count

        # Store in session for later refactoring (limited data)
        session["repo_url"] = repo_url
        session["temp_dir"] = temp_dir
        # Store function indices mapping
        session["func_count"] = len(all_functions)

        # Store all function data as JSON for the refactor endpoint
        funcs_data = []
        for f in all_functions:
            funcs_data.append({
                "index": len(funcs_data),
                "name": f["name"],
                "full_name": f["full_name"],
                "rel_path": f.get("rel_path", f["file_path"]),
                "start_line": f["start_line"],
                "num_lines": f.get("num_lines", 0),
                "is_bad_smell": f["is_bad_smell"],
                "smell_probability": f["smell_probability"],
                "display_smells": f["display_smells"],
                "smell_count": f["smell_count"],
                "source_code": f["source_code"],
            })
        # Store to a temp file (session is too small)
        funcs_json = SCRIPT_DIR / ".funcs_cache.json"
        funcs_json.write_text(json.dumps(funcs_data, indent=2), encoding="utf-8")

        return render_template(
            "functions.html",
            repo_url=repo_url,
            functions=all_functions,
            bad_count=bad_count,
            good_count=good_count,
            total=len(all_functions),
        )

    except Exception as e:
        error = f"{type(e).__name__}: {str(e)}"
        traceback.print_exc()
        _cleanup_temp(temp_dir)
        session.pop("temp_dir", None)
        return render_template("index.html", error=error, repo_url=repo_url)


@app.route("/function/<int:func_index>")
def function_detail(func_index):
    """Show detailed view of a single function."""
    funcs_json = SCRIPT_DIR / ".funcs_cache.json"
    if not funcs_json.exists():
        return render_template("index.html", error="Session expired. Please analyze a repo again.")

    functions = json.loads(funcs_json.read_text(encoding="utf-8"))
    if func_index < 0 or func_index >= len(functions):
        return render_template("index.html", error="Function not found.")

    func = functions[func_index]
    return jsonify(func)


@app.route("/refactor", methods=["POST"])
def refactor():
    """Refactor a selected function via OpenRouter API."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    func_index = data.get("func_index")
    # Use user-provided API key, or fall back to default from .env
    api_key = data.get("api_key", "").strip()
    if not api_key:
        api_key = os.environ.get("DEFAULT_API_KEY", "").strip()

    if func_index is None:
        return jsonify({"error": "No function selected"}), 400

    funcs_json = SCRIPT_DIR / ".funcs_cache.json"
    if not funcs_json.exists():
        return jsonify({"error": "Session expired. Please analyze a repo again."}), 400

    functions = json.loads(funcs_json.read_text(encoding="utf-8"))
    if func_index < 0 or func_index >= len(functions):
        return jsonify({"error": "Function not found."}), 400

    func = functions[func_index]
    source_code = func["source_code"]
    func_name = func["name"]

    # ── Step 1: LLM Recommendation ──────────────────────────────────────
    try:
        ranking = get_ranking(source_code, func_name)
        if ranking:
            best_llm = ranking[0]
        else:
            best_llm = {
                "model_key": "gpt_oss",
                "display_name": "GPT-OSS 120B",
                "quality_score": 5.0,
                "composite": 50.0,
            }
    except Exception as e:
        best_llm = {
            "model_key": "gpt_oss",
            "display_name": "GPT-OSS 120B",
            "quality_score": 5.0,
            "composite": 50.0,
        }
        ranking = [best_llm]

    # ── Step 2: No API key → show recommendation only ──────────────────
    if not api_key:
        return jsonify({
            "status": "needs_api_key",
            "func_index": func_index,
            "func_name": func_name,
            "recommendation": best_llm,
            "ranking": ranking[:3],
        })

    # ── Step 3: Refactor ────────────────────────────────────────────────
    try:
        result = refactor_function(
            code=source_code,
            model_key=best_llm["model_key"],
            api_key=api_key,
            max_retries=2,
            timeout=120,
        )

        if result["success"] and verify_refactored_code(source_code, result["refactored_code"]):
            refactored_code = result["refactored_code"]

            # Detect smells in refactored code
            refactored_smells_raw = detect_code_smells(refactored_code)
            refactored_smells = _format_smells(refactored_smells_raw)
            refactored_smell_count = len(refactored_smells)
            original_smell_count = len(func.get("display_smells", []))
            smells_fixed = original_smell_count - refactored_smell_count

            # Get line counts
            orig_lines = len(source_code.split("\n"))
            refact_lines = len(refactored_code.split("\n"))

            return jsonify({
                "status": "success",
                "func_index": func_index,
                "func_name": func_name,
                "original_code": source_code,
                "refactored_code": refactored_code,
                "recommendation": best_llm,
                "original_smell_count": original_smell_count,
                "refactored_smell_count": refactored_smell_count,
                "smells_fixed": smells_fixed,
                "refactored_smells": refactored_smells,
                "original_lines": orig_lines,
                "refactored_lines": refact_lines,
                "usage": result.get("usage"),
            })

        else:
            error_msg = result.get("error", "Refactoring produced invalid Python code.")
            return jsonify({
                "status": "error",
                "func_index": func_index,
                "func_name": func_name,
                "error": error_msg,
                "recommendation": best_llm,
            }), 500

    except Exception as e:
        return jsonify({
            "status": "error",
            "func_index": func_index,
            "func_name": func_name,
            "error": f"{type(e).__name__}: {str(e)}",
            "recommendation": best_llm,
        }), 500


@app.route("/_health")
def health():
    return "ok", 200


if __name__ == "__main__":
    # Clean up stale cache on start
    cache = SCRIPT_DIR / ".funcs_cache.json"
    if cache.exists():
        cache.unlink()

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)