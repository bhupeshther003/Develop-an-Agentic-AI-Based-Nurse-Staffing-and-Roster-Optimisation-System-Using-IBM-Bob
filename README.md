# 🏥 Nurse Staffing & Roster Optimisation System

> **Agentic AI-based nurse scheduling powered by IBM Bob, IBM Granite & Python**

---

## 📋 Project Overview

A **40-bed hospital unit** needs a two-week nursing roster that ensures:
- Adequate shift coverage across Morning, Afternoon, Night, and Long Day shifts
- Appropriate role and skill distribution (RN / EN / Senior RN)
- Balanced workloads across the entire nursing team
- Compliance with rest periods, consecutive-day limits, and weekly hour caps
- Final approval by an authorised hospital manager before the roster goes live

This system uses **8 specialised AI Agents** orchestrated through IBM Bob and IBM Granite to automate roster generation, validation, fairness analysis, and reporting — while keeping the final scheduling authority with the human manager.

---

## 🤖 AI Agent Architecture

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | **Staffing Data Analysis** | Analyse staff roles, qualifications, availability, and preferences |
| 2 | **Coverage Planning** | Determine required nurses and skill mix per shift per day |
| 3 | **Roster Generation** | Generate a draft 14-day roster using a greedy constraint-aware algorithm |
| 4 | **Constraint Validation** | Check rest periods, consecutive days, weekly hours, and coverage minimums |
| 5 | **Workload Fairness** | Compare shift counts, night shifts, weekends, and hours across staff |
| 6 | **Roster Optimisation** | Suggest specific reassignments to fix violations and improve balance |
| 7 | **Reporting** | Produce coverage matrix, violation report, fairness summary, and revision log |
| 8 | **Human Review Workflow** | Submit roster to authorised manager for approval or rejection |

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| AI / LLM | IBM Granite (`ibm/granite-13b-instruct-v2`) via Watson ML |
| Agent Orchestration | IBM Bob (Agentic AI) |
| Backend | Python 3.11 + FastAPI |
| Database | SQLite (synthetic staffing data) |
| Frontend | HTML5 + CSS3 + Vanilla JavaScript |
| Server | Uvicorn (ASGI) |

---

## 📁 Project Structure

```
Healthcare P3/
│
├── main.py              # FastAPI app — all API routes
├── agents.py            # 8 AI agents (core business logic)
├── granite_ai.py        # IBM Granite integration via Watson ML
├── database.py          # SQLite setup + synthetic data seeding
├── test_agents.py       # Agent test script
├── requirements.txt     # Python dependencies
├── nurse_roster.db      # SQLite database (auto-created on first run)
│
└── static/
    └── index.html       # Full single-page dashboard (HTML/CSS/JS)
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python **3.11+** installed
- Internet access (for IBM Granite API calls)

### 2. Clone / Download the project
```powershell
cd "d:\OneDrive - Edunet Foundation\Desktop\IBM BOB\Healthcare P3"
```

### 3. Install dependencies
```powershell
pip install fastapi uvicorn python-multipart jinja2 aiofiles requests numpy pandas python-dotenv pydantic
```

Or use the requirements file:
```powershell
pip install -r requirements.txt
```

### 4. Run the application
```powershell
python main.py
```

You will see:
```
INFO:     Started server process [XXXX]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080
```

### 5. Open in browser
```
http://127.0.0.1:8080
```

---

## 🚀 Quick Start — Using the Dashboard

Once the app is running at `http://127.0.0.1:8080`:

1. **Click "⚡ Run All Agents"** in the top-right — this automatically:
   - Analyses the 20 synthetic staff members
   - Plans shift coverage for 14 days
   - Generates the draft roster
   - Validates all scheduling constraints
   - Analyses workload fairness
   - Generates optimisation recommendations
   - Produces the full report

2. **Browse the Roster Grid** — see every nurse assigned to every shift for all 14 days

3. **Review Violations** — see critical and warning-level scheduling issues

4. **View Optimisation recommendations** — AI-suggested fixes for each violation

5. **Submit for Approval** — enter the manager's name and submit for human review

6. **Manager approves or rejects** — roster only becomes operational after approval

---

## 📊 Staffing Data (Synthetic)

The system seeds **20 synthetic nursing staff** on first run:

| Role | Count | Grades |
|------|-------|--------|
| Registered Nurse (RN) | 13 | Senior (7), Junior (6) |
| Enrolled Nurse (EN) | 7 | Grade 1 (3), Grade 2 (4) |

**Skills available:** IV Therapy, Wound Care, ICU, Triage, Paediatrics, Oncology, Palliative Care, Emergency, Basic Care, Medication Admin, Personal Care, Vital Signs

**Shift types:**

| Shift | Time | Duration |
|-------|------|----------|
| Morning | 07:00 – 15:00 | 8 hours |
| Afternoon | 15:00 – 23:00 | 8 hours |
| Night | 23:00 – 07:00 | 8 hours |
| Long Day | 07:00 – 19:00 | 12 hours |

---

## 📏 Scheduling Constraints Enforced

| Rule | Limit |
|------|-------|
| Minimum rest between shifts | 10 hours |
| Maximum consecutive working days | 5 days |
| Maximum weekly hours | 48 hours |
| Minimum RNs per Morning shift | 3 |
| Minimum RNs per Afternoon/Night shift | 2 |
| Minimum ENs per shift | 1–2 |
| Senior RN required every shift | ✅ Mandatory |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard (HTML) |
| GET | `/api/health` | Health check |
| GET | `/api/agent/staffing-analysis` | Agent 1 — Staffing analysis |
| GET | `/api/agent/coverage-planning` | Agent 2 — Coverage plan |
| GET | `/api/agent/generate-roster` | Agent 3 — Generate roster |
| GET | `/api/agent/validate` | Agent 4 — Validate constraints |
| GET | `/api/agent/workload-fairness` | Agent 5 — Workload fairness |
| GET | `/api/agent/optimise` | Agent 6 — Optimisation |
| GET | `/api/agent/report` | Agent 7 — Full report |
| GET | `/api/roster` | Get roster grid |
| GET | `/api/roster/summary` | Roster KPI summary |
| GET | `/api/staff` | All staff |
| GET | `/api/staff/{id}` | Staff detail + shifts |
| GET | `/api/violations` | All violations |
| POST | `/api/violations/{id}/resolve` | Mark violation resolved |
| POST | `/api/approval/submit` | Submit for manager review |
| POST | `/api/approval/{id}/decision` | Approve or reject |
| GET | `/api/approval/status` | Current approval status |

Interactive API docs: **`http://127.0.0.1:8080/docs`**

---

## 🧪 Testing

Run the agent test script to verify all 8 agents work correctly:

```powershell
python test_agents.py
```

Expected output:
```
============================================================
NURSE STAFFING & ROSTER OPTIMISATION — AGENT TEST
============================================================
[1] Staffing Data Analysis Agent  ...  PASS
[2] Coverage Planning Agent        ...  PASS
[3] Roster Generation Agent        ...  PASS
[4] Constraint Validation Agent    ...  PASS
[5] Workload Fairness Agent        ...  PASS
[6] Roster Optimisation Agent      ...  PASS
[7] Reporting Agent                ...  PASS
[8] Human Review — Submit          ...  PASS
============================================================
ALL AGENTS PASSED SUCCESSFULLY!
============================================================
```

---

## 🔐 IBM Granite AI Configuration

The system uses **IBM Granite 13B Instruct v2** for AI-powered explanations. Credentials are pre-configured in [`granite_ai.py`](granite_ai.py):

| Setting | Value |
|---------|-------|
| Project ID | `ccd108e4-4978-4065-8a4c-0bbaa4faf2fd` |
| Endpoint | `https://au-syd.ml.cloud.ibm.com` |
| Model | `ibm/granite-13b-instruct-v2` |

> **Offline fallback:** If the IBM Watson ML API is unreachable, the system automatically returns structured AI-style responses so the app remains fully functional.

---

## ⚠️ Important Guardrails

- ✅ All data is **synthetic** — no real patient or staff data used
- ✅ AI-generated rosters are **drafts only** — must be approved by an authorised manager
- ✅ Unresolved violations are **flagged** and cannot be silently ignored
- ✅ Workload balancing **never overrides** mandatory staffing or rest requirements
- ✅ All proposed changes are **documented** with rationale

---

## 👨‍💻 Development

Built with **IBM Bob** (Agentic AI development assistant) as part of the **Edunet Foundation Healthcare P3** project.

**Technology:** IBM Bob · IBM Granite · Agentic AI · FastAPI · SQLite · Python 3.11

---

## 📄 License

This project is developed for **educational purposes** as part of the IBM Bob Healthcare capstone project. Synthetic data only. Not for operational clinical use.
