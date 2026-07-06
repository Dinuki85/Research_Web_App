<h1 align="center">
  <br>
  <img src="https://img.shields.io/badge/CodeRefactor-AI-6366f1?style=for-the-badge&logo=python&logoColor=white" alt="CodeRefactor AI">
  <br>
  CodeRefactor AI
  <br>
</h1>

<h4 align="center">An AI-powered web tool that analyzes Python repositories, detects code smells, and refactors code using Large Language Models.</h4>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.0+-000000?style=flat-square&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/scikit--learn-1.3+-F7931E?style=flat-square&logo=scikit-learn&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenRouter-API-412991?style=flat-square&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-usage">Usage</a> •
  <a href="#-project-structure">Project Structure</a> •
  <a href="#-models-setup">Models Setup</a> •
  <a href="#-tech-stack">Tech Stack</a>
</p>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Language Detection** | Automatically detects the programming language of a repository and only proceeds with Python |
| 🧬 **Code Smell Detection** | ML-powered analysis identifies 9 types of code quality issues |
| 🤖 **AI Refactoring** | Uses OpenRouter API to suggest clean, refactored versions of bad code |
| 📁 **File Filtering** | Optionally target a specific file inside the repository |
| 🏆 **LLM Ranking** | Recommends the best AI model for each specific function |
| ✅ **Code Verification** | Validates that AI output is syntactically correct Python before showing it |

---

## 🔄 How It Works

```
 User Input (GitHub URL + optional file)
            │
            ▼
    ┌───────────────┐
    │  Clone / Scan │  Clones the repo into a temp directory
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │   Language    │  Counts .py vs .java/.js/.cs/.php files
    │   Detection   │  ──► If NOT Python → Stop + Show Error
    └───────┬───────┘
            │ Python ✅
            ▼
    ┌───────────────┐
    │ Scan Functions│  Extracts all Python functions via AST parsing
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ Smell Detection│ ML model scores each function (9 smell types)
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │  Results Page │  Sorted by severity (bad smells first)
    └───────┬───────┘
            │  User clicks "Refactor"
            ▼
    ┌───────────────┐
    │ LLM Ranking   │  Picks the best AI model for this code
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ AI Refactoring│  Calls OpenRouter API → verifies output
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ Before / After│  Side-by-side diff + smells fixed count
    └───────────────┘
```

---

## 🧠 Code Smells Detected

<details>
<summary><b>Click to expand — 9 Smell Types</b></summary>

| # | Smell | Description |
|---|---|---|
| 1 | **Long Method** | Function has too many lines |
| 2 | **Long Parameter List** | Too many parameters in function signature |
| 3 | **Deep Nesting** | Excessive indentation levels |
| 4 | **Magic Numbers** | Hardcoded numeric values without named constants |
| 5 | **No Docstring** | Missing function documentation |
| 6 | **No Type Hints** | Missing parameter/return type annotations |
| 7 | **Long Lines** | Lines exceeding 79 characters (PEP 8) |
| 8 | **Commented-out Code** | Dead code left in comments |
| 9 | **Poor Naming** | Single-letter or non-descriptive variable names |

</details>

---

## 🚀 Installation

### Prerequisites

- Python 3.11+
- Git installed and on PATH
- An [OpenRouter](https://openrouter.ai/) API key (for refactoring)

### Steps

**1. Clone this repository**
```bash
git clone https://github.com/Dinuki85/Research_Web_App.git
cd Research_Web_App
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set up model files**

> ⚠️ Model files are not included in this repo due to file size. See [Models Setup](#-models-setup) below.

**4. Create your `.env` file**
```bash
# Create .env in the webapp/ root
echo "DEFAULT_API_KEY=your_openrouter_api_key_here" > .env
```

**5. Run the app**
```bash
python app.py
```

**6. Open in browser**
```
http://127.0.0.1:5000
```

---

## 📖 Usage

### Analyze an Entire Repository
1. Paste a GitHub URL into the **Repository URL** field
2. Leave the **Specific File** field empty
3. Click **Analyze**

```
Example: https://github.com/username/my-python-project
```

### Analyze a Specific File
1. Paste the GitHub URL
2. Enter a relative file path in the **Specific File** field
3. Click **Analyze**

```
Example file path: src/utils.py
```

### Refactor a Function
1. After analysis, click any function card marked with ⚠️ (bad smell)
2. Enter your OpenRouter API key
3. Click **Refactor** — the AI rewrites the function and shows you the diff

---

## 📁 Project Structure

```
webapp/
│
├── app.py                      # Flask app — routes and pipeline orchestration
├── requirements.txt            # Python dependencies
├── .env                        # API keys (not in git)
├── .gitignore
│
├── src/                        # Core pipeline modules
│   ├── repo_analyzer.py        # Git clone + Python function extraction (AST)
│   ├── language_detector.py    # Language detection (extension-based + ML model)
│   ├── code_smell_detector.py  # ML smell classification (SVM)
│   ├── llm_recommender.py      # LLM ranking and smell rule engine
│   └── refactoring_engine.py   # OpenRouter API call + code verification
│
├── models/                     # ML model files (not in git — download separately)
│   ├── best_language_classifier.joblib   # Language classifier bundle
│   ├── smell_svm.pkl                     # Code smell SVM model
│   ├── smell_scaler.pkl
│   ├── quality_*.pkl                     # Code quality models
│   └── metrics_*.pkl                     # Metrics prediction models
│
├── templates/
│   ├── base.html               # Shared layout
│   ├── index.html              # Landing page (URL input form)
│   └── functions.html          # Results dashboard
│
└── static/
    └── style.css               # App styling
```

---

## 🗃️ Models Setup

Since model files are large (50–100 MB each), they are **not included in this repository**. You need to obtain them separately.

### Option A: Train Them Yourself

| Model | Training Notebook |
|---|---|
| `best_language_classifier.joblib` | `language_classification.ipynb` |
| `smell_svm.pkl` + `smell_scaler.pkl` | `model_synthetic.ipynb` |
| `quality_*.pkl` | Quality scoring notebook |
| `metrics_*.pkl` | Metrics prediction notebook |

After training, place all model files inside the `models/` folder.

### Option B: Download Pre-trained Models

Contact the repository owner or check the project's shared drive link for pre-trained model files.

### Verify Models Are in Place
```bash
ls models/
# Should show: best_language_classifier.joblib, smell_svm.pkl, etc.
```

---

## 🛠️ Tech Stack

<details>
<summary><b>Backend</b></summary>

| Library | Purpose |
|---|---|
| **Flask 3.0** | Web framework and routing |
| **scikit-learn** | ML models for smell detection and language classification |
| **joblib** | Model serialization and loading |
| **scipy** | Sparse matrix operations for TF-IDF features |
| **python-dotenv** | Environment variable management |

</details>

<details>
<summary><b>Language Detection</b></summary>

Two-stage approach:
1. **File extension counting** — Fast, runs on raw repo files before any scanning
2. **TF-IDF + ML classifier** — Content-based fallback using char/word n-grams

Supports: **Python, Java, JavaScript, TypeScript, C#, PHP, Ruby, Go, C++, C, Rust**

</details>

<details>
<summary><b>AI Refactoring</b></summary>

- Connects to **OpenRouter API** to access multiple LLMs
- A custom **LLM ranking system** selects the best model per function type
- Refactored output is verified with `ast.parse()` before being shown to the user

</details>

---

## 🔐 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DEFAULT_API_KEY` | Optional | OpenRouter API key (users can also provide their own in the UI) |
| `PORT` | Optional | Port to run Flask on (default: `5000`) |
| `FLASK_DEBUG` | Optional | Enable debug mode — `1` (default) or `0` |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

This project is part of a research initiative. See the repository owner for licensing details.

---

<p align="center">
  Built with ❤️ using Flask + scikit-learn + OpenRouter API
</p>
