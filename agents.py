"""
Agentic AI Nurse Staffing and Roster Optimisation System
Core agents: Staffing Analysis, Coverage Planning, Roster Generation,
             Constraint Validation, Workload Fairness, Optimisation, Reporting
"""

import sqlite3
import random
from datetime import date, timedelta, datetime
from database import get_conn, DB_PATH


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1 — Staffing Data Analysis Agent
# ══════════════════════════════════════════════════════════════════════════════

def staffing_analysis_agent() -> dict:
    """Analyse all staff: roles, qualifications, availability summary."""
    conn = get_conn()
    c    = conn.cursor()

    staff = c.execute("SELECT * FROM staff").fetchall()
    staff_list = []
    for s in staff:
        avail_count = c.execute(
            "SELECT COUNT(*) FROM availability WHERE staff_id=? AND available=1", (s["id"],)
        ).fetchone()[0]
        staff_list.append({
            "id": s["id"], "name": s["name"], "role": s["role"],
            "grade": s["grade"], "skills": s["skills"].split(","),
            "contract_hours": s["contract_hours"],
            "available_days": avail_count,
        })

    rn_count     = sum(1 for s in staff_list if s["role"] == "RN")
    en_count     = sum(1 for s in staff_list if s["role"] == "EN")
    senior_count = sum(1 for s in staff_list if "Senior" in s["grade"])
    all_skills   = set()
    for s in staff_list:
        all_skills.update(s["skills"])

    avg_hours = sum(s["contract_hours"] for s in staff_list) / len(staff_list) if staff_list else 0

    conn.close()
    return {
        "agent": "Staffing Data Analysis",
        "total": len(staff_list),
        "rn_count": rn_count,
        "en_count": en_count,
        "senior_count": senior_count,
        "avg_hours": round(avg_hours, 1),
        "skills": sorted(all_skills),
        "staff": staff_list,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 2 — Coverage Planning Agent
# ══════════════════════════════════════════════════════════════════════════════

COVERAGE_REQUIREMENTS = {
    # shift_name: (min_rn, min_en, min_senior_rn)
    "Morning":   {"min_rn": 3, "min_en": 2, "min_senior": 1},
    "Afternoon": {"min_rn": 2, "min_en": 2, "min_senior": 1},
    "Night":     {"min_rn": 2, "min_en": 1, "min_senior": 1},
    "Long Day":  {"min_rn": 3, "min_en": 2, "min_senior": 1},
}


def coverage_planning_agent(roster_start: date, roster_end: date) -> dict:
    """Determine required staffing for each shift/day in the roster period."""
    conn  = get_conn()
    c     = conn.cursor()
    shifts = c.execute("SELECT * FROM shifts").fetchall()
    conn.close()

    plan   = []
    total_required = 0
    day = roster_start
    while day <= roster_end:
        day_str = day.isoformat()
        is_weekend = day.weekday() >= 5
        for sh in shifts:
            req = COVERAGE_REQUIREMENTS.get(sh["name"], {"min_rn":2,"min_en":1,"min_senior":1})
            # Weekend Night needs at least 1 senior RN
            required = {
                "date": day_str,
                "day_name": day.strftime("%A"),
                "is_weekend": is_weekend,
                "shift_id": sh["id"],
                "shift_name": sh["name"],
                "shift_time": f"{sh['start_time']}–{sh['end_time']}",
                "min_rn": req["min_rn"],
                "min_en": req["min_en"],
                "min_senior": req["min_senior"],
                "total_required": req["min_rn"] + req["min_en"],
            }
            plan.append(required)
            total_required += required["total_required"]
        day += timedelta(days=1)

    return {
        "agent": "Coverage Planning",
        "roster_start": roster_start.isoformat(),
        "roster_end":   roster_end.isoformat(),
        "total_days": (roster_end - roster_start).days + 1,
        "total_required_slots": total_required,
        "requirements": plan,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 3 — Roster Generation Agent
# ══════════════════════════════════════════════════════════════════════════════

def roster_generation_agent(roster_start: date, roster_end: date) -> dict:
    """
    Generate a draft two-week roster using a greedy constraint-aware algorithm.
    Assigns staff to shifts respecting availability, role requirements, and
    distributes workload evenly.
    """
    conn = get_conn()
    c    = conn.cursor()

    # Clear any existing draft roster
    c.execute("DELETE FROM roster")
    c.execute("DELETE FROM violations")
    conn.commit()

    shifts = {row["id"]: dict(row) for row in c.execute("SELECT * FROM shifts").fetchall()}
    staff  = [dict(row) for row in c.execute("SELECT * FROM staff").fetchall()]

    # Build availability lookup
    avail_rows = c.execute("SELECT * FROM availability").fetchall()
    avail = {}
    for row in avail_rows:
        avail[(row["staff_id"], row["date"])] = {
            "available": row["available"],
            "preferred_shift": row["preferred_shift"],
        }

    # Track assignments
    assignments = []          # list of (staff_id, shift_id, date_str)
    staff_shift_count   = {s["id"]: 0 for s in staff}
    staff_last_shift_end = {}  # staff_id -> datetime of last shift end
    staff_consecutive   = {s["id"]: 0 for s in staff}
    staff_last_date     = {s["id"]: None for s in staff}

    coverage_plan = coverage_planning_agent(roster_start, roster_end)["requirements"]

    for slot in coverage_plan:
        day_str  = slot["date"]
        shift_id = slot["shift_id"]
        shift    = shifts[shift_id]
        day_date = date.fromisoformat(day_str)

        # Determine how many RN and EN are needed
        needed_rn = slot["min_rn"]
        needed_en = slot["min_en"]

        # Separate eligible staff by role
        def eligible(staff_member, role):
            sid = staff_member["id"]
            av  = avail.get((sid, day_str), {})
            if not av.get("available", 1):
                return False
            if staff_member["role"] != role:
                return False
            # Already assigned this day?
            if any(a[0] == sid and a[2] == day_str for a in assignments):
                return False
            # Consecutive day limit (max 5 consecutive working days)
            if staff_consecutive.get(sid, 0) >= 5:
                return False
            return True

        rn_eligible = [s for s in staff if eligible(s, "RN")]
        en_eligible = [s for s in staff if eligible(s, "EN")]

        # Sort by fewest shifts (fairness) then preference match
        def score(s, role):
            pref = avail.get((s["id"], day_str), {}).get("preferred_shift")
            pref_bonus = -5 if pref == shift["name"] else 0
            senior_bonus = -3 if "Senior" in s["grade"] and role == "RN" else 0
            return staff_shift_count[s["id"]] + pref_bonus + senior_bonus

        rn_eligible.sort(key=lambda s: score(s, "RN"))
        en_eligible.sort(key=lambda s: score(s, "EN"))

        assigned_this_slot = []

        for rn in rn_eligible[:needed_rn]:
            assignments.append((rn["id"], shift_id, day_str))
            assigned_this_slot.append(rn["id"])
            staff_shift_count[rn["id"]] += 1

        for en in en_eligible[:needed_en]:
            assignments.append((en["id"], shift_id, day_str))
            assigned_this_slot.append(en["id"])
            staff_shift_count[en["id"]] += 1

        # Update consecutive tracking
        for sid in assigned_this_slot:
            last = staff_last_date.get(sid)
            if last and (day_date - last).days == 1:
                staff_consecutive[sid] = staff_consecutive.get(sid, 0) + 1
            else:
                staff_consecutive[sid] = 1
            staff_last_date[sid] = day_date

    # Persist roster
    for (staff_id, shift_id, day_str) in assignments:
        c.execute(
            "INSERT INTO roster (staff_id, shift_id, roster_date, status) VALUES (?,?,?,?)",
            (staff_id, shift_id, day_str, "draft")
        )
    conn.commit()

    total_assigned = len(assignments)
    conn.close()

    return {
        "agent": "Roster Generation",
        "status": "draft_generated",
        "roster_start": roster_start.isoformat(),
        "roster_end": roster_end.isoformat(),
        "total_assignments": total_assigned,
        "shift_distribution": staff_shift_count,
        "message": f"Draft roster generated with {total_assigned} shift assignments across 14 days.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 4 — Constraint Validation Agent
# ══════════════════════════════════════════════════════════════════════════════

def constraint_validation_agent() -> dict:
    """
    Validate the current roster against:
    - Rest period between shifts (min 10 hours)
    - Max consecutive working days (5)
    - Maximum weekly hours (48)
    - Minimum coverage per shift/day
    - Senior RN presence per shift
    """
    conn = get_conn()
    c    = conn.cursor()

    roster  = c.execute("""
        SELECT r.*, s.name AS shift_name, s.start_time, s.end_time, s.duration_hours,
               st.name AS staff_name, st.role, st.grade, st.contract_hours
        FROM roster r
        JOIN shifts s ON r.shift_id = s.id
        JOIN staff st ON r.staff_id = st.id
        ORDER BY r.staff_id, r.roster_date
    """).fetchall()

    violations = []

    # Group by staff
    from collections import defaultdict
    staff_assignments = defaultdict(list)
    for row in roster:
        staff_assignments[row["staff_id"]].append(dict(row))

    # Check 1: Rest period between consecutive shifts (min 10 hrs)
    SHIFT_HOURS = {"Morning": (7, 15), "Afternoon": (15, 23), "Night": (23, 31), "Long Day": (7, 19)}

    for sid, entries in staff_assignments.items():
        entries_sorted = sorted(entries, key=lambda x: x["roster_date"])
        for i in range(1, len(entries_sorted)):
            prev = entries_sorted[i - 1]
            curr = entries_sorted[i]
            prev_end_h   = SHIFT_HOURS.get(prev["shift_name"], (0, 8))[1]
            curr_start_h = SHIFT_HOURS.get(curr["shift_name"], (0, 8))[0]
            prev_date = date.fromisoformat(prev["roster_date"])
            curr_date = date.fromisoformat(curr["roster_date"])
            days_diff = (curr_date - prev_date).days
            if days_diff == 0:
                rest_hours = 0  # double-booked same day
            elif days_diff == 1:
                rest_hours = (24 - prev_end_h) + curr_start_h
            else:
                rest_hours = 999

            if rest_hours < 10:
                violations.append({
                    "staff_id": sid,
                    "staff_name": prev["staff_name"],
                    "type": "Insufficient Rest",
                    "severity": "critical",
                    "description": (
                        f"{prev['staff_name']} has only {rest_hours}h rest between "
                        f"{prev['shift_name']} on {prev['roster_date']} and "
                        f"{curr['shift_name']} on {curr['roster_date']} (minimum 10h required)."
                    ),
                })

    # Check 2: Max consecutive days
    for sid, entries in staff_assignments.items():
        dates = sorted(set(date.fromisoformat(e["roster_date"]) for e in entries))
        consecutive = 1
        max_consec   = 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days == 1:
                consecutive += 1
                max_consec = max(max_consec, consecutive)
            else:
                consecutive = 1
        if max_consec > 5:
            violations.append({
                "staff_id": sid,
                "staff_name": entries[0]["staff_name"],
                "type": "Excessive Consecutive Days",
                "severity": "warning",
                "description": (
                    f"{entries[0]['staff_name']} is scheduled for {max_consec} consecutive days "
                    "(maximum is 5 days without a day off)."
                ),
            })

    # Check 3: Weekly hours check
    for sid, entries in staff_assignments.items():
        week1 = [e for e in entries if date.fromisoformat(e["roster_date"]).weekday() <= 6
                 and (date.fromisoformat(e["roster_date"]) - date.fromisoformat(entries[0]["roster_date"])).days < 7]
        w1_hours = sum(e["duration_hours"] for e in week1)
        if w1_hours > 48:
            violations.append({
                "staff_id": sid,
                "staff_name": entries[0]["staff_name"],
                "type": "Excessive Weekly Hours",
                "severity": "warning",
                "description": (
                    f"{entries[0]['staff_name']} is scheduled for {w1_hours}h in week 1 "
                    f"(maximum 48h per week per hospital policy)."
                ),
            })

    # Check 4: Shift coverage – ensure minimum staffing met
    from collections import Counter
    shift_day_staff = defaultdict(list)
    for row in roster:
        key = (row["roster_date"], row["shift_id"], row["shift_name"])
        shift_day_staff[key].append({"role": row["role"], "grade": row["grade"]})

    for (day_str, shift_id, shift_name), staff_list in shift_day_staff.items():
        req = COVERAGE_REQUIREMENTS.get(shift_name, {"min_rn": 2, "min_en": 1, "min_senior": 1})
        rn_count     = sum(1 for s in staff_list if s["role"] == "RN")
        en_count     = sum(1 for s in staff_list if s["role"] == "EN")
        senior_count = sum(1 for s in staff_list if "Senior" in s["grade"] and s["role"] == "RN")

        if rn_count < req["min_rn"]:
            violations.append({
                "staff_id": None, "staff_name": "N/A",
                "type": "Coverage Gap – RN",
                "severity": "critical",
                "description": (
                    f"{shift_name} shift on {day_str} has only {rn_count} RN(s) "
                    f"(minimum {req['min_rn']} required)."
                ),
            })
        if en_count < req["min_en"]:
            violations.append({
                "staff_id": None, "staff_name": "N/A",
                "type": "Coverage Gap – EN",
                "severity": "warning",
                "description": (
                    f"{shift_name} shift on {day_str} has only {en_count} EN(s) "
                    f"(minimum {req['min_en']} required)."
                ),
            })
        if senior_count < req["min_senior"]:
            violations.append({
                "staff_id": None, "staff_name": "N/A",
                "type": "No Senior RN on Shift",
                "severity": "critical",
                "description": (
                    f"{shift_name} shift on {day_str} has no Senior RN "
                    f"(at least 1 required per shift)."
                ),
            })

    # Persist violations
    c.execute("DELETE FROM violations")
    for v in violations:
        c.execute(
            "INSERT INTO violations (staff_id, violation_type, description, severity) VALUES (?,?,?,?)",
            (v.get("staff_id"), v["type"], v["description"], v["severity"])
        )
    conn.commit()
    conn.close()

    critical = [v for v in violations if v["severity"] == "critical"]
    warnings = [v for v in violations if v["severity"] == "warning"]

    return {
        "agent": "Constraint Validation",
        "total_violations": len(violations),
        "critical": len(critical),
        "warnings": len(warnings),
        "violations": violations,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 5 — Workload Fairness Agent
# ══════════════════════════════════════════════════════════════════════════════

def workload_fairness_agent() -> dict:
    """Analyse shift distribution, night shifts, weekends, and hours across staff."""
    conn = get_conn()
    c    = conn.cursor()

    roster = c.execute("""
        SELECT r.staff_id, r.roster_date, s.name AS shift_name, s.duration_hours,
               st.name AS staff_name, st.role, st.contract_hours
        FROM roster r
        JOIN shifts s ON r.shift_id = s.id
        JOIN staff st ON r.staff_id = st.id
    """).fetchall()

    from collections import defaultdict
    staff_data = defaultdict(lambda: {
        "total_shifts": 0, "total_hours": 0.0,
        "night_shifts": 0, "weekend_shifts": 0,
        "morning_shifts": 0, "afternoon_shifts": 0,
        "long_day_shifts": 0, "name": "", "role": "", "contract_hours": 0
    })

    for row in roster:
        sid  = row["staff_id"]
        d    = date.fromisoformat(row["roster_date"])
        data = staff_data[sid]
        data["name"]           = row["staff_name"]
        data["role"]           = row["role"]
        data["contract_hours"] = row["contract_hours"]
        data["total_shifts"]  += 1
        data["total_hours"]   += row["duration_hours"]
        if row["shift_name"] == "Night":
            data["night_shifts"] += 1
        if d.weekday() >= 5:
            data["weekend_shifts"] += 1
        if row["shift_name"] == "Morning":
            data["morning_shifts"] += 1
        elif row["shift_name"] == "Afternoon":
            data["afternoon_shifts"] += 1
        elif row["shift_name"] == "Long Day":
            data["long_day_shifts"] += 1

    if not staff_data:
        conn.close()
        return {"agent": "Workload Fairness", "error": "No roster data found."}

    shifts_list = [d["total_shifts"] for d in staff_data.values()]
    hours_list  = [d["total_hours"]  for d in staff_data.values()]
    nights_list = [d["night_shifts"] for d in staff_data.values()]
    wknds_list  = [d["weekend_shifts"] for d in staff_data.values()]

    import statistics
    avg_shifts = statistics.mean(shifts_list)
    std_dev    = statistics.stdev(shifts_list) if len(shifts_list) > 1 else 0

    fairness_score = max(0, 100 - int(std_dev * 10))

    staff_summary = []
    for sid, data in staff_data.items():
        imbalance = "Over-assigned" if data["total_shifts"] > avg_shifts + 2 else \
                    "Under-assigned" if data["total_shifts"] < avg_shifts - 2 else "Balanced"
        staff_summary.append({
            "staff_id": sid,
            "name": data["name"],
            "role": data["role"],
            "total_shifts": data["total_shifts"],
            "total_hours": round(data["total_hours"], 1),
            "night_shifts": data["night_shifts"],
            "weekend_shifts": data["weekend_shifts"],
            "morning_shifts": data["morning_shifts"],
            "afternoon_shifts": data["afternoon_shifts"],
            "long_day_shifts": data["long_day_shifts"],
            "contract_hours": data["contract_hours"],
            "imbalance": imbalance,
        })

    conn.close()
    return {
        "agent": "Workload Fairness",
        "fairness_score": fairness_score,
        "avg_shifts": round(avg_shifts, 1),
        "max_shifts": max(shifts_list),
        "min_shifts": min(shifts_list),
        "std_dev": round(std_dev, 2),
        "avg_hours": round(statistics.mean(hours_list), 1),
        "night_shifts": {"max": max(nights_list), "min": min(nights_list), "avg": round(statistics.mean(nights_list), 1)},
        "weekend_shifts": {"max": max(wknds_list), "min": min(wknds_list), "avg": round(statistics.mean(wknds_list), 1)},
        "staff_summary": sorted(staff_summary, key=lambda x: -x["total_shifts"]),
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 6 — Roster Optimisation Agent
# ══════════════════════════════════════════════════════════════════════════════

def roster_optimisation_agent() -> dict:
    """
    Suggest specific roster changes to:
    - Fix critical violations (rest period, coverage gaps)
    - Improve workload balance
    Returns a list of actionable recommendations.
    """
    conn = get_conn()
    c    = conn.cursor()

    violations = c.execute(
        "SELECT * FROM violations WHERE resolved=0"
    ).fetchall()

    fairness = workload_fairness_agent()
    staff_summary = {s["staff_id"]: s for s in fairness.get("staff_summary", [])}
    avg = fairness.get("avg_shifts", 0)

    recommendations = []
    action_counter = 1

    # Fix coverage gaps
    for v in violations:
        if "Coverage Gap" in v["violation_type"]:
            # Parse date and shift from description
            desc = v["description"]
            rec = {
                "id": action_counter,
                "type": "Coverage Fix",
                "priority": "High",
                "description": desc,
                "action": (
                    "Identify available staff of the required role/grade on this date "
                    "and assign them to fill the coverage gap. Check part-time staff "
                    "or consider overtime assignment with manager approval."
                ),
                "estimated_impact": "Resolves critical coverage violation",
            }
            recommendations.append(rec)
            action_counter += 1

    # Fix rest period violations
    for v in violations:
        if "Rest" in v["violation_type"]:
            rec = {
                "id": action_counter,
                "type": "Rest Period Correction",
                "priority": "Critical",
                "description": v["description"],
                "action": (
                    "Swap one of the conflicting shifts to a staff member with sufficient "
                    "rest, or reschedule the second shift to achieve minimum 10-hour gap."
                ),
                "estimated_impact": "Eliminates rest-period violation; improves staff wellbeing",
            }
            recommendations.append(rec)
            action_counter += 1

    # Fix excessive consecutive days
    for v in violations:
        if "Consecutive" in v["violation_type"]:
            rec = {
                "id": action_counter,
                "type": "Consecutive Days Correction",
                "priority": "Medium",
                "description": v["description"],
                "action": (
                    "Insert a rest day in the middle of the consecutive run by swapping "
                    "the shift to an available colleague."
                ),
                "estimated_impact": "Reduces fatigue risk and policy violation",
            }
            recommendations.append(rec)
            action_counter += 1

    # Workload rebalancing
    over_assigned  = [s for s in fairness.get("staff_summary", []) if s["imbalance"] == "Over-assigned"]
    under_assigned = [s for s in fairness.get("staff_summary", []) if s["imbalance"] == "Under-assigned"]

    if over_assigned and under_assigned:
        over_names  = ", ".join(s["name"] for s in over_assigned[:3])
        under_names = ", ".join(s["name"] for s in under_assigned[:3])
        recommendations.append({
            "id": action_counter,
            "type": "Workload Rebalancing",
            "priority": "Medium",
            "description": f"Workload imbalance detected. Over-assigned: {over_names}. Under-assigned: {under_names}.",
            "action": (
                f"Transfer 1–2 shifts from over-assigned staff ({over_names}) "
                f"to under-assigned staff ({under_names}) of the same role and grade."
            ),
            "estimated_impact": f"Improves workload fairness score from {fairness.get('fairness_score')}% toward 90%+",
        })
        action_counter += 1

    # Night-shift equity
    ns = fairness.get("night_shifts", {})
    if ns.get("max", 0) - ns.get("min", 0) > 3:
        recommendations.append({
            "id": action_counter,
            "type": "Night Shift Equity",
            "priority": "Low",
            "description": (
                f"Night shift spread is uneven: max {ns.get('max')} vs min {ns.get('min')} per staff member."
            ),
            "action": (
                "Redistribute night shifts so no nurse has more than 2 extra nights compared "
                "to the team average. Use a rotating night-shift schedule for fairness."
            ),
            "estimated_impact": "Improves morale and reduces long-term burnout",
        })
        action_counter += 1

    conn.close()
    return {
        "agent": "Roster Optimisation",
        "total_recommendations": len(recommendations),
        "recommendations": recommendations,
        "summary": (
            f"Generated {len(recommendations)} optimisation recommendations addressing "
            f"{len(violations)} violations and workload imbalances."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 7 — Reporting Agent
# ══════════════════════════════════════════════════════════════════════════════

def reporting_agent() -> dict:
    """Generate comprehensive roster report: coverage matrix, violations, workload."""
    conn = get_conn()
    c    = conn.cursor()

    roster_rows = c.execute("""
        SELECT r.roster_date, s.name AS shift_name, st.name AS staff_name,
               st.role, st.grade, r.status
        FROM roster r
        JOIN shifts s ON r.shift_id = s.id
        JOIN staff st ON r.staff_id = st.id
        ORDER BY r.roster_date, s.name, st.name
    """).fetchall()

    violations   = c.execute("SELECT * FROM violations").fetchall()
    approval_row = c.execute("SELECT * FROM approvals ORDER BY id DESC LIMIT 1").fetchone()

    # Coverage matrix per day/shift
    from collections import defaultdict
    coverage_matrix = defaultdict(lambda: defaultdict(list))
    for row in roster_rows:
        coverage_matrix[row["roster_date"]][row["shift_name"]].append({
            "name": row["staff_name"],
            "role": row["role"],
            "grade": row["grade"],
        })

    # Summary stats
    total_shifts_filled = len(roster_rows)
    unique_dates = len(coverage_matrix)

    conn.close()

    fairness = workload_fairness_agent()
    validation = constraint_validation_agent()
    optimisation = roster_optimisation_agent()

    return {
        "agent": "Reporting",
        "generated_at": datetime.now().isoformat(),
        "roster_summary": {
            "total_shifts_assigned": total_shifts_filled,
            "roster_days": unique_dates,
            "coverage_matrix": {k: dict(v) for k, v in coverage_matrix.items()},
        },
        "constraint_report": {
            "total_violations": validation["total_violations"],
            "critical": validation["critical"],
            "warnings": validation["warnings"],
            "violations": validation["violations"],
        },
        "workload_report": fairness,
        "optimisation_report": optimisation,
        "approval_status": dict(approval_row) if approval_row else {"status": "pending"},
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 8 — Human Review Workflow Agent
# ══════════════════════════════════════════════════════════════════════════════

def submit_for_approval(manager_name: str, comments: str, roster_start: str, roster_end: str) -> dict:
    """Submit the roster for human manager review and approval."""
    conn = get_conn()
    c    = conn.cursor()

    c.execute("""
        INSERT INTO approvals (roster_date_start, roster_date_end, status, manager_name, comments)
        VALUES (?, ?, 'pending', ?, ?)
    """, (roster_start, roster_end, manager_name, comments))
    approval_id = c.lastrowid
    conn.commit()
    conn.close()

    return {
        "agent": "Human Review Workflow",
        "approval_id": approval_id,
        "status": "submitted_for_review",
        "manager": manager_name,
        "message": (
            f"Roster ({roster_start} – {roster_end}) submitted to {manager_name} for review. "
            "Manager must approve or reject before the roster becomes operational."
        ),
    }


def approve_roster(approval_id: int, decision: str, manager_name: str, comments: str) -> dict:
    """Manager approves or rejects the roster."""
    conn = get_conn()
    c    = conn.cursor()

    status = "approved" if decision == "approve" else "rejected"
    now    = datetime.now().isoformat()
    c.execute("""
        UPDATE approvals SET status=?, manager_name=?, comments=?, approved_at=?
        WHERE id=?
    """, (status, manager_name, comments, now, approval_id))

    if status == "approved":
        c.execute("UPDATE roster SET status='approved'")

    conn.commit()
    conn.close()

    return {
        "agent": "Human Review Workflow",
        "approval_id": approval_id,
        "status": status,
        "manager": manager_name,
        "timestamp": now,
        "message": (
            f"Roster has been {status} by {manager_name}. "
            + ("All shift assignments are now operational." if status == "approved"
               else "Roster returned for revision.")
        ),
    }


def get_roster_grid(roster_start: date, roster_end: date) -> dict:
    """Return a structured grid of roster data for the UI."""
    conn = get_conn()
    c    = conn.cursor()

    rows = c.execute("""
        SELECT r.id, r.roster_date, r.status, r.notes,
               s.name AS shift_name, s.start_time, s.end_time,
               st.id AS staff_id, st.name AS staff_name, st.role, st.grade
        FROM roster r
        JOIN shifts s ON r.shift_id = s.id
        JOIN staff st ON r.staff_id = st.id
        ORDER BY r.roster_date, s.name
    """).fetchall()

    shifts = [dict(row) for row in c.execute("SELECT * FROM shifts").fetchall()]
    staff  = [dict(row) for row in c.execute("SELECT * FROM staff").fetchall()]
    conn.close()

    from collections import defaultdict
    grid = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grid[row["roster_date"]][row["shift_name"]].append({
            "roster_id": row["id"],
            "staff_id":  row["staff_id"],
            "name":      row["staff_name"],
            "role":      row["role"],
            "grade":     row["grade"],
            "status":    row["status"],
        })

    dates = []
    d = roster_start
    while d <= roster_end:
        dates.append(d.isoformat())
        d += timedelta(days=1)

    return {
        "dates": dates,
        "shifts": [s["name"] for s in shifts],
        "grid": {k: dict(v) for k, v in grid.items()},
        "staff": staff,
    }
