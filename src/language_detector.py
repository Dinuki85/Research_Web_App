"""
Language Detector
=================
Detects the dominant programming language of a repository's functions
using a pre-trained TF-IDF + ML classifier bundle.

Supported languages: Python, Java, C#, JavaScript, PHP

Behaviour:
  - Samples up to MAX_SAMPLE_SIZE functions from the scanned repo.
  - Predicts the language for each sampled function.
  - Returns the majority-vote language and a confidence score.
  - The /analyze route uses this to gate: only Python repos proceed.
"""

import re
import sys
import warnings
import joblib
from pathlib import Path
from collections import Counter
from scipy.sparse import hstack, csr_matrix

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent.parent   # webapp/
MODELS_DIR  = SCRIPT_DIR / "models"
LANG_MODEL_PATH = MODELS_DIR / "best_language_classifier.joblib"

# How many functions to sample for the majority-vote decision
MAX_SAMPLE_SIZE = 10

# ── Global bundle cache (load once) ──────────────────────────────────────────
_bundle = None


def _load_bundle() -> dict:
    """Load the classifier bundle from disk (cached after first call)."""
    global _bundle
    if _bundle is not None:
        return _bundle

    if not LANG_MODEL_PATH.exists():
        print(
            f"[language_detector] Model not found at: {LANG_MODEL_PATH}\n"
            "  Place 'best_language_classifier.joblib' inside webapp/models/",
            file=sys.stderr,
        )
        sys.exit(1)

    _bundle = joblib.load(str(LANG_MODEL_PATH))
    return _bundle


# ── Internal helpers ──────────────────────────────────────────────────────────

_EXT_RE = re.compile(r"\S+\.(py|java|cs|php|js)\b", re.IGNORECASE)


def _strip_file_extensions(text: str) -> str:
    """Remove file-path tokens that could leak the language label."""
    return _EXT_RE.sub("", text)


def _build_feature_vector(func_name: str, source_code: str, num_lines: int):
    """
    Replicate the exact feature engineering from the training notebook:
      combined_text = function_name (lower) + cleaned code
      features      = tfidf_char + tfidf_word + lines_count
    """
    bundle = _load_bundle()
    tfidf_char = bundle["tfidf_char"]
    tfidf_word = bundle["tfidf_word"]

    cleaned_code  = _strip_file_extensions(source_code)
    combined_text = func_name.lower() + " " + cleaned_code

    x_char  = tfidf_char.transform([combined_text])
    x_word  = tfidf_word.transform([combined_text])

    return hstack([x_char, x_word])


def _predict_one(func_name: str, source_code: str, num_lines: int) -> str:
    """Predict the programming language of a single function."""
    bundle      = _load_bundle()
    model       = bundle["model"]
    class_names = bundle["class_names"]

    X           = _build_feature_vector(func_name, source_code, num_lines)
    label_idx   = model.predict(X)[0]
    return class_names[label_idx]


def predict_file_language(file_name: str, source_code: str) -> str:
    """Predict the programming language of an entire file."""
    bundle      = _load_bundle()
    model       = bundle["model"]
    class_names = bundle["class_names"]

    num_lines = len(source_code.splitlines())
    X         = _build_feature_vector(file_name, source_code, num_lines)
    label_idx = model.predict(X)[0]
    return class_names[label_idx]


# ── Public API ────────────────────────────────────────────────────────────────

def detect_repo_language(functions: list) -> tuple:
    """
    Detect the dominant programming language of a repository.

    Samples up to MAX_SAMPLE_SIZE functions, predicts each one's language,
    and returns the majority-vote result.

    Args:
        functions: List of function dicts from scan_functions().
                   Each dict must have 'name', 'source_code', and optionally
                   'num_lines'.

    Returns:
        (dominant_language: str, confidence: float)
        e.g. ("Python", 0.9) or ("Java", 0.7)

        dominant_language is a string from:
          ['C#', 'Java', 'JavaScript', 'PHP', 'Python']
        confidence is the fraction of sampled functions predicted as that language.
    """
    if not functions:
        return ("Python", 0.0)   # nothing to analyse — let it pass through

    # Sample evenly across the function list
    step      = max(1, len(functions) // MAX_SAMPLE_SIZE)
    sampled   = functions[::step][:MAX_SAMPLE_SIZE]

    predictions = []
    for func in sampled:
        name       = func.get("name", "")
        code       = func.get("source_code", "")
        num_lines  = func.get("num_lines", len(code.splitlines()))
        try:
            lang = _predict_one(name, code, num_lines)
            predictions.append(lang)
        except Exception:
            # Skip functions that fail to vectorize
            continue

    if not predictions:
        return ("Python", 0.0)

    counts           = Counter(predictions)
    dominant_lang    = counts.most_common(1)[0][0]
    confidence       = counts[dominant_lang] / len(predictions)

    return (dominant_lang, confidence)


def is_python_repo(functions: list) -> tuple:
    """
    Convenience wrapper: returns (is_python: bool, detected_lang: str, confidence: float).

    Use this in app.py to gate the analysis pipeline.

    Example:
        ok, lang, conf = is_python_repo(all_functions)
        if not ok:
            return render_template("index.html",
                error=f"Detected {lang} repository. Only Python is supported.")
    """
    lang, confidence = detect_repo_language(functions)
    return (lang.lower() == "python", lang, confidence)


# ── Extension-based gate (fast, runs on raw repo files) ──────────────────────

# Maps file extension → display language name
_EXT_LANG_MAP = {
    ".java": "Java",
    ".js":   "JavaScript",
    ".cs":   "C#",
    ".php":  "PHP",
    ".cpp":  "C++",
    ".c":    "C",
}


def detect_language_by_extensions(repo_path) -> tuple:
    """
    Count source files by extension to determine the dominant language.

    This runs BEFORE scan_functions() on the raw cloned repo, making it
    a reliable gate for non-Python repos.

    Args:
        repo_path: pathlib.Path — root of the cloned/local repository.

    Returns:
        (is_python: bool, dominant_lang: str, confidence: float)

        confidence = fraction of code files that belong to the dominant language.
        e.g. (False, "Java", 0.92)  or  (True, "Python", 0.88)
    """
    repo_path = Path(repo_path)

    py_count    = len(list(repo_path.rglob("*.py")))
    other_counts = {}

    for ext, lang in _EXT_LANG_MAP.items():
        count = len(list(repo_path.rglob(f"*{ext}")))
        if count:
            other_counts[lang] = other_counts.get(lang, 0) + count

    total_other = sum(other_counts.values())
    total_all   = py_count + total_other

    if total_all == 0:
        # No recognised code files at all — let it through, scan_functions
        # will handle the "no functions found" case.
        return (True, "Python", 0.0)

    if py_count >= total_other:
        confidence = py_count / total_all
        return (True, "Python", confidence)

    # Find dominant non-Python language
    dominant_lang = max(other_counts, key=other_counts.get)
    confidence    = other_counts[dominant_lang] / total_all
    return (False, dominant_lang, confidence)
