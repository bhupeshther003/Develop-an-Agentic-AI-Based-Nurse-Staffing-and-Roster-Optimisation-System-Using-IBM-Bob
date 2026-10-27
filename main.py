"""
FastAPI application — Nurse Staffing & Roster Optimisation System
All API routes for agents, roster management, and reporting.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date, timedelta
from typing import Optional
from contextlib import asynccontextmanager
import os

from database import init_db, get_conn
from agents import (
    staffing_analysis_agent,
    coverage_planning_agent,
    roster_generation_agent,
    constraint_validation_agent,
    workload_fairness_agent,
    roster_optimisation_agent,
    reporting_agent,
    submit_for_approval,
    approve_roster,
    get_roster_grid,
)
import granite_ai

# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Nurse Staffing & Roster Optimisation System",
    description="Agentic AI-based roster management using IBM Granite",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Helper: get roster date range ─────────────────────────────────────────────

def get_roster_range():
    today   = date.today()
    monday  = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    return monday, monday + timedelta(days=13)


# ══════════════════════════════════════════════════════════════════════════════
# FRONTEND
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════════════
# AGENT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/agent/staffing-analysis")
def api_staffing_analysis():
    result = staffing_analysis_agent()
    # Enrich with IBM Granite AI insight
    try:
        ai_insight = granite_ai.analyse_staffing_data(result)
        result["ai_insight"] = ai_insight
    except Exception as e:
        result["ai_insight"] = f"AI insight unavailable: {str(e)[:100]}"
    return result


@app.get("/api/agent/coverage-planning")
def api_coverage_planning():
    start, end = get_roster_range()
    result = coverage_planning_agent(start, end)
    try:
        coverage_data = {
            "start": result["roster_start"], "end": result["roster_end"],
            "total_required": result["total_required_slots"],
            "total_filled": _count_current_assignments(),
            "coverage_pct": _calc_coverage_pct(),
            "uncovered": result["total_required_slots"] - _count_current_assignments(),
            "breakdown": "Morning: 5/day, Afternoon: 4/day, Night: 3/day, Long Day: 5/day",
        }
        result["ai_insight"] = granite_ai.analyse_coverage(coverage_data)
    except Exception as e:
        result["ai_insight"] = f"AI insight unavailable: {str(e)[:100]}"
    return result


@app.get("/api/agent/generate-roster")
def api_generate_roster():
    start, end = get_roster_range()
    result = roster_generation_agent(start, end)
    return result


@app.get("/api/agent/validate")
def api_validate():
    result = constraint_validation_agent()
    try:
        if result["violations"]:
            result["ai_insight"] = granite_ai.explain_violations(result["violations"])
        else:
            result["ai_insight"] = "✅ No violations detected. Roster meets all scheduling constraints."
    except Exception as e:
        result["ai_insight"] = f"AI insight unavailable: {str(e)[:100]}"
    return result


@app.get("/api/agent/workload-fairness")
def api_workload_fairness():
    result = workload_fairness_agent()
    try:
        result["ai_insight"] = granite_ai.analyse_workload_fairness(result)
    except Exception as e:
        result["ai_insight"] = f"AI insight unavailable: {str(e)[:100]}"
    return result


@app.get("/api/agent/optimise")
def api_optimise():
    validation = constraint_validation_agent()
    fairness   = workload_fairness_agent()
    context = {
        "violation_count": validation["total_violations"],
        "uncovered_shifts": validation["critical"],
        "overworked":  [s["name"] for s in fairness.get("staff_summary", []) if s["imbalance"] == "Over-assigned"],
        "underworked": [s["name"] for s in fairness.get("staff_summary", []) if s["imbalance"] == "Under-assigned"],
    }
    result = roster_optimisation_agent()
    try:
        result["ai_insight"] = granite_ai.generate_optimisation_recommendations(context)
    except Exception as e:
        result["ai_insight"] = f"AI insight unavailable: {str(e)[:100]}"
    return result


@app.get("/api/agent/report")
def api_report():
    return reporting_agent()


# ══════════════════════════════════════════════════════════════════════════════
# ROSTER CRUD
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/roster")
def api_get_roster():
    start, end = get_roster_range()
    return get_roster_grid(start, end)


@app.get("/api/roster/summary")
def api_roster_summary():
    conn = get_conn()
    c    = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM roster").fetchone()[0]
    approved = c.execute("SELECT COUNT(*) FROM roster WHERE status='approved'").fetchone()[0]
    violations = c.execute("SELECT COUNT(*) FROM violations WHERE resolved=0").fetchone()[0]
    critical   = c.execute("SELECT COUNT(*) FROM violations WHERE severity='critical' AND resolved=0").fetchone()[0]
    conn.close()
    start, end = get_roster_range()
    return {
        "total_assignments": total,
        "approved_assignments": approved,
        "open_violations": violations,
        "critical_violations": critical,
        "roster_start": start.isoformat(),
        "roster_end": end.isoformat(),
        "roster_status": "approved" if approved == total and total > 0 else "draft",
    }


@app.get("/api/staff")
def api_get_staff():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM staff").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/staff/{staff_id}")
def api_get_staff_detail(staff_id: int):
    conn = get_conn()
    c    = conn.cursor()
    staff = c.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(404, "Staff not found")
    shifts = c.execute("""
        SELECT r.roster_date, s.name AS shift_name, s.start_time, s.end_time, r.status
        FROM roster r JOIN shifts s ON r.shift_id=s.id
        WHERE r.staff_id=? ORDER BY r.roster_date
    """, (staff_id,)).fetchall()
    avail = c.execute(
        "SELECT * FROM availability WHERE staff_id=? ORDER BY date", (staff_id,)
    ).fetchall()
    conn.close()
    return {
        "staff": dict(staff),
        "roster": [dict(r) for r in shifts],
        "availability": [dict(a) for a in avail],
    }


@app.get("/api/shifts")
def api_get_shifts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM shifts").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/violations")
def api_get_violations():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM violations ORDER BY severity DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


class ResolveViolationBody(BaseModel):
    resolution_notes: str


@app.post("/api/violations/{vid}/resolve")
def api_resolve_violation(vid: int, body: ResolveViolationBody):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("UPDATE violations SET resolved=1, description=description||' | Resolved: '||? WHERE id=?",
              (body.resolution_notes, vid))
    conn.commit()
    conn.close()
    return {"status": "resolved", "violation_id": vid}


# ══════════════════════════════════════════════════════════════════════════════
# APPROVAL WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

class SubmitApprovalBody(BaseModel):
    manager_name: str
    comments: Optional[str] = ""


@app.post("/api/approval/submit")
def api_submit_approval(body: SubmitApprovalBody):
    start, end = get_roster_range()
    return submit_for_approval(body.manager_name, body.comments, start.isoformat(), end.isoformat())


class ApproveBody(BaseModel):
    decision: str  # "approve" or "reject"
    manager_name: str
    comments: Optional[str] = ""


@app.post("/api/approval/{approval_id}/decision")
def api_approve(approval_id: int, body: ApproveBody):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "Decision must be 'approve' or 'reject'")
    return approve_roster(approval_id, body.decision, body.manager_name, body.comments)


@app.get("/api/approval/status")
def api_approval_status():
    conn = get_conn()
    row  = conn.execute("SELECT * FROM approvals ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"status": "not_submitted"}


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY
# ══════════════════════════════════════════════════════════════════════════════

def _count_current_assignments() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM roster").fetchone()[0]
    conn.close()
    return n


def _calc_coverage_pct() -> float:
    start, end = get_roster_range()
    plan   = coverage_planning_agent(start, end)
    filled = _count_current_assignments()
    required = plan["total_required_slots"]
    return round((filled / required * 100), 1) if required > 0 else 0.0


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Nurse Staffing & Roster Optimisation System", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
