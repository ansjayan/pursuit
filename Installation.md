


# Installation

## 1. Prerequisites

The recommended environment is:

```text
Python 3.12
Git
Node.js / npx
uv / uvx
```

`uvx` is required for the DuckDuckGo MCP server.

`npx` is required for the Defuddle MCP server.

Verify them:

```bash
python --version
uvx --version
node --version
npx --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/ansjayan/pursuit
cd pursuit
```



---

## 3. Create a Virtual Environment

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

---

## 4. Install Python Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The project uses the Gemini integration provided through Strands:

```text
strands-agents[gemini]
```

---

## 5. Install `uv`

If `uvx` is not already available, install `uv` using the installation method appropriate for your operating system.

After installation verify:

```bash
uvx --version
```

---

## 6. Install Node.js

Install a current Node.js distribution if `node` and `npx` are not already available.

Verify:

```bash
node --version
npx --version
```

---

# Gemini API Configuration

PURSUIT requires a Google Gemini API key. Create one free using google ai studio

Copy:

```text
.env.example
```

to:

```text
.env
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

Then edit `.env`:

```dotenv
GEMINI_API_KEY=your_api_key_here
```

Do not commit `.env`.

---

Getting a free Gemini API key from [Google AI Studio](https://aistudio.google.com/) is quick and straightforward. 
Follow these steps:

### Step-by-Step Guide

1. **Go to Google AI Studio:** Open your browser and navigate to the [Google AI Studio](https://aistudio.google.com/) platform.
2. **Sign In:** Log in using your personal Google account.
3. **Accept Terms:** If it's your first time visiting, review and accept the Terms of Service when prompted.
4. **Navigate to API Keys:** Look at the left-hand sidebar and click on the **"Get API key"** button (or go directly to the API keys section).
5. **Create the Key:** Click on **"Create API key"**.
6. **Select a Project:** A pop-up will ask you to choose whether to create the key in a *new Google Cloud project* or an *existing project* (no billing account or credit card is required for the free tier).
7. **Copy and Save:** Your free API key will be generated instantly. Copy it and store it securely. Avoid exposing it in public repositories or client-side code.

> [!NOTE]
> The free tier gives you access to Gemini models with generous rate limits (measured by requests per minute and per day), perfect for prototyping, testing, and developing personal projects.


---
# Database Initialization

The runtime database is intentionally not committed to GitHub.

PURSUIT creates its SQLite database locally:

```text
data/pursuit.db
```

The application initializes the database on startup.

For explicit initialization before launching the UI, run:

```bash
python -m app.database
```

This is recommended when testing a fresh installation.

---

# Run PURSUIT

Start the Streamlit application from the repository root:

```bash
streamlit run main.py
```

Streamlit will display the local application URL in the terminal.

Open it in a browser.

---

# First-Time Walkthrough

For the fastest evaluation of the project:

### 1. Create an account

Use the normal email/password registration flow.

No Google OAuth configuration is required.

### 2. Complete the profile

Add professional information relevant to opportunity evaluation.

### 3. Upload a résumé or supporting document

PURSUIT ingests the document into the personal evidence system.

### 4. Discover one opportunity

For a fast smoke test, use:

```text
Opportunity type: JOB
Maximum opportunities: 1
```

Using one opportunity reduces API usage and makes the full agent pipeline easier to observe.

### 5. Allow the pipeline to run

PURSUIT performs:

```text
Discovery
   ↓
Research
   ↓
Personal Fit
   ↓
Value
   ↓
Effort & Risk
   ↓
Decision
```

### 6. View Analysis

Open the resulting opportunity analysis to inspect:

- recommendation,
- score,
- personal fit,
- requirement analysis,
- learning value,
- portfolio value,
- effort,
- risks,
- reasoning,
- next actions.

### 7. Open Original

Use the original-source link to inspect the opportunity page used during discovery/research.

---

# Local MCP Test

The web research layer can also be tested independently:

```bash
python tools/web_research.py
```

This verifies access to:

- DuckDuckGo MCP
- Defuddle MCP

and performs a small search test.

---

# Compile Check

To compile individual critical modules:

```bash
python -m py_compile main.py
python -m py_compile pipeline.py
python -m py_compile agents/discovery_agent.py
python -m py_compile agents/research_agent.py
python -m py_compile agents/personal_agent.py
python -m py_compile agents/value_agent.py
python -m py_compile agents/effort_agent.py
python -m py_compile agents/decision_agent.py
python -m py_compile app/database.py
python -m py_compile app/scoring.py
```
