




# PURSUIT

### AI Opportunity Discovery & Decision Intelligence

PURSUIT is a multi-agent AI system built with the **AWS Strands Agents SDK** that helps people discover professional opportunities, understand them, evaluate their personal fit, estimate their value and risk, and decide what is actually worth pursuing.

Instead of giving users another list of search results, PURSUIT attempts to answer a harder question:

> **Which opportunities are worth my time, and why?**

PURSUIT is submitted to the **Professional Agents** track.

---

## The Problem

Finding professional opportunities is fragmented and time-consuming.

A person may need to:

- search multiple websites,
- filter irrelevant or duplicate listings,
- determine whether an opportunity is still actionable,
- read long job or program descriptions,
- compare requirements against their own experience,
- identify skill gaps,
- judge whether an opportunity is worth the effort,
- consider learning and portfolio value,
- assess risks and deadlines,
- and finally decide whether to pursue it.

Traditional search engines and job boards primarily help with **discovery**.

PURSUIT is designed to help with the complete decision workflow.

---

## Who PURSUIT Is For

PURSUIT is designed for professionals, job seekers, students, career changers, developers, researchers, and other people searching for professional growth opportunities.

It supports multiple opportunity categories, including:

- Jobs
- Hackathons
- Grants
- Programs
- Freelance opportunities

A user can create a profile, upload supporting documents such as a résumé, and allow PURSUIT to evaluate opportunities against evidence from their own background.

---

# What PURSUIT Does

PURSUIT runs a multi-stage agent workflow:

```text
User Profile + Documents
          │
          ▼
     Discovery Agent
          │
          ▼
      Research Agent
          │
          ▼
     Personal Agent
          │
          ├──────────► User RAG Evidence
          │
          ▼
       Value Agent
          │
          ▼
   Effort & Risk Agent
          │
          ▼
     Decision Agent
          │
          ▼
 Deterministic Scoring
          │
          ▼
 PURSUE / REVIEW / REJECT
```

Each agent has a specialized responsibility instead of asking one large prompt to perform the entire workflow.

---

# AWS Strands Agents SDK

PURSUIT is built around the **Strands Agents SDK**.

Strands is used as the orchestration and agent framework for the system's AI reasoning stages.

The architecture includes:

- Strands Agents
- structured agent outputs
- agent tools
- MCP integration
- external web-search tools
- webpage research tools
- retrieval-augmented personal intelligence
- specialized multi-agent responsibilities
- deterministic scoring after agent reasoning

The objective is not simply to call an LLM from an application. PURSUIT gives individual agents different responsibilities and tools within an end-to-end professional decision workflow.

---

# Agent Architecture

## 1. Discovery Agent

The Discovery Agent searches for actionable professional opportunities based on:

- requested opportunity categories,
- user preferences,
- target number of opportunities,
- search coverage,
- source quality.

It searches the public web through a Strands tool backed by a DuckDuckGo MCP server.

The Discovery Agent attempts to reject:

- personal profile pages,
- non-opportunity pages,
- irrelevant search results,
- malformed results,
- results without usable source URLs,
- duplicate opportunities.

Discovery stops when the requested opportunity targets have been satisfied or the configured search budget has been exhausted.

---

## 2. Research Agent

Discovery results are leads, not trusted final evidence.

The Research Agent opens the actual opportunity URL and extracts structured information from the underlying page.

It can identify information such as:

- title,
- organization,
- category,
- description,
- requirements,
- eligibility,
- location,
- work arrangement,
- deadline,
- reward,
- submission information,
- supporting evidence.

Webpage extraction is performed through a Strands tool backed by the **Defuddle MCP server**.

This separation helps prevent search-result snippets from being treated as complete opportunity descriptions.

---

## 3. Personal Agent

The Personal Agent compares researched opportunity requirements against evidence from the user's profile and uploaded documents.

Possible requirement states include:

```text
Match
Partial
No Match
Unknown
```

An important design rule is:

> Missing evidence is not automatically treated as failure.

If PURSUIT cannot establish whether a user meets a requirement, the requirement can remain `Unknown` instead of being incorrectly classified as a skill gap.

---

## 4. Personal RAG

Uploaded user documents are converted into searchable evidence.

PURSUIT uses:

- document ingestion,
- deterministic text chunking,
- ChromaDB,
- semantic retrieval,
- per-user filtering.

The architecture is:

```text
Uploaded document
       │
       ▼
 Text extraction
       │
       ▼
    Chunking
       │
       ▼
   ChromaDB
       │
       ▼
Semantic retrieval
       │
       ▼
 Personal Agent
```

SQLite remains the source of truth for application data, while ChromaDB acts as the semantic retrieval layer.

Retrieval is isolated by user ID so one user's profile evidence is not intentionally searched as evidence for another user.

---

## 5. Value Agent

Not every opportunity is valuable simply because the user qualifies.

The Value Agent evaluates dimensions such as:

### Learning Value

How much useful skill development is supported by the opportunity evidence?

### Portfolio Value

How much meaningful professional or project evidence could the opportunity potentially create?

The agent produces evidence-grounded qualitative assessments that are subsequently converted into deterministic component scores.

---

## 6. Effort & Risk Agent

The Effort & Risk Agent evaluates the practical cost and supported risks of pursuing an opportunity.

It considers evidence such as:

- application complexity,
- explicit deliverables,
- preparation requirements,
- personal-fit gaps,
- deadlines,
- participation requirements,
- project workload,
- explicit eligibility concerns.

The agent is instructed not to invent risks such as relocation, visa problems, salary issues, company culture, or competition unless those concerns are supported by the supplied opportunity evidence.

---

## 7. Decision Agent

The Decision Agent receives the results of the upstream analysis.

However, the LLM does **not** have final control over the numerical score.

PURSUIT separates:

```text
AI reasoning
     ↓
structured evidence
     ↓
deterministic Python scoring
```

The Decision Agent explains the resulting decision and generates evidence-grounded next actions.

It cannot change the final deterministic score.

---

# Deterministic Scoring

The current final score combines:

| Component | Weight |
|---|---:|
| Personal Fit | 35% |
| Learning Value | 20% |
| Portfolio Value | 20% |
| Effort | 10% |
| Risk | 15% |

The final recommendation is calculated in application code:

```text
Score >= 70       → PURSUE
Score 50–69       → REVIEW
Score < 50        → REJECT
```

This makes the final recommendation more reproducible and auditable than allowing an LLM to freely generate a score.

---

# MCP-Powered Web Research

PURSUIT uses the Strands MCP client to connect to external MCP servers.

## DuckDuckGo MCP

Used by Discovery for public web search.

```text
Discovery Agent
      ↓
Strands Tool
      ↓
search_web()
      ↓
Strands MCPClient
      ↓
DuckDuckGo MCP
```

## Defuddle MCP

Used by Research to extract readable content from opportunity pages.

```text
Research Agent
      ↓
Strands Tool
      ↓
fetch_webpage()
      ↓
Strands MCPClient
      ↓
Defuddle MCP
```

This means the web research layer is integrated with the Strands tool ecosystem rather than being only an unrelated scraper outside the agent architecture.

---

# Resumable Agent Pipeline

Multi-agent workflows can fail because of:

- model API limits,
- network errors,
- inaccessible webpages,
- MCP failures,
- temporary provider errors.

PURSUIT persists stage progress.

For example:

```text
RESEARCH       COMPLETE
PERSONAL_FIT   COMPLETE
VALUE          FAILED
EFFORT_RISK    PENDING
DECISION       PENDING
```

A later retry can resume from the incomplete stage instead of unnecessarily repeating completed work.

This is especially useful when operating with limited API quotas.

---

# Opportunity History

PURSUIT stores evaluated opportunities and their analysis.

Users can review opportunities and track workflow states such as:

- Interested
- Watch
- Applied
- Dismissed

Opportunity cards can provide access to:

- the original source,
- detailed analysis,
- recommendation,
- score,
- personal fit,
- gaps,
- next actions.

---

# Technology Stack

| Layer | Technology |
|---|---|
| Agent framework | AWS Strands Agents SDK |
| LLM provider | Google Gemini |
| UI | Streamlit |
| Structured outputs | Pydantic |
| Application database | SQLite |
| Vector database | ChromaDB |
| Web search | DuckDuckGo MCP |
| Webpage extraction | Defuddle MCP |
| MCP integration | Strands MCPClient |
| Document parsing | PyPDF / python-docx |
| Language | Python 3.12 |

---

# Project Structure

```text
pursuit/
│
├── main.py
├── pipeline.py
├── requirements.txt
├── README.md
├── LICENSE
├── .env.example
├── .gitignore
│
├── agents/
│   ├── discovery_agent.py
│   ├── research_agent.py
│   ├── personal_agent.py
│   ├── value_agent.py
│   ├── effort_agent.py
│   └── decision_agent.py
│
├── app/
│   ├── account_service.py
│   ├── constants.py
│   ├── database.py
│   └── scoring.py
│
├── config/
│   └── models.py
│
├── rag/
│   ├── ingestion.py
│   └── vector_store.py
│
├── tools/
│   └── web_research.py
│
└── utils/
    └── json_utils.py
```

Runtime data is generated locally and is not committed to the repository.

---

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
git clone https://github.com/YOUR_GITHUB_USERNAME/pursuit.git
cd pursuit
```

Replace `YOUR_GITHUB_USERNAME` with the repository owner.

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

PURSUIT requires a Google Gemini API key.

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

---

# Privacy and Data Isolation

PURSUIT stores application data locally in SQLite and semantic profile evidence locally in ChromaDB.

Personal retrieval is scoped by user ID.

Secrets are loaded from environment variables and should not be committed to source control.

The following runtime artifacts are excluded from the public repository:

```text
.env
data/
*.db
*.sqlite
*.sqlite3
```

---

# Design Principles

PURSUIT follows several principles:

### Evidence before inference

Agents should reason from retrieved opportunity and user evidence rather than invent missing facts.

### Unknown is not failure

Missing evidence should remain uncertain when appropriate instead of automatically becoming a negative qualification.

### Search results are leads

Search snippets are not treated as authoritative opportunity research. The Research Agent attempts to inspect the underlying page.

### Agents reason; code scores

LLMs perform interpretation and evidence-grounded reasoning.

Python performs the final numerical calculation.

### Resume instead of restart

Completed pipeline stages are persisted so temporary failures do not necessarily require repeating the entire workflow.

### User-specific intelligence

The same opportunity can receive different personal-fit analysis for different users because PURSUIT evaluates it against each user's own evidence.

---

# Limitations

PURSUIT is a prototype and has several practical limitations.

- Public web search does not guarantee exhaustive internet coverage.
- Some websites may block automated extraction.
- Search results and opportunity pages can become outdated.
- Free model/API quotas may limit repeated evaluations.
- LLM-generated analysis can still contain errors.
- Semantic retrieval depends on the quality of uploaded documents.
- Opportunity availability should be verified on the original source before acting.
- Scores are decision-support signals, not guarantees of professional outcomes.

---

# Why PURSUIT Matters

The internet already contains enormous numbers of opportunities.

The harder problem is deciding:

```text
Is this real?
Is it relevant to me?
Do I meet the requirements?
What am I missing?
What would I gain?
How much effort will it take?
What are the risks?
Should I spend my time pursuing it?
```

PURSUIT turns those questions into an agentic workflow.

Its goal is not simply to help people **find more opportunities**.

Its goal is to help them **make better decisions about which opportunities deserve their time**.

---

# License

This project is licensed under the **MIT License**.

See [`LICENSE`](LICENSE) for details.

---

# Hackathon Track

**Professional Agents**

PURSUIT targets a repetitive, research-heavy, judgment-heavy professional workflow: finding and evaluating opportunities.

It uses the AWS Strands Agents SDK to coordinate specialized AI agents that perform discovery, research, personal evidence retrieval, value assessment, risk assessment, and decision explanation as an end-to-end workflow.






