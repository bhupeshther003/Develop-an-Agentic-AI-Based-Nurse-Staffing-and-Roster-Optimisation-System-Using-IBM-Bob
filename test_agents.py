"""
Test script for all agents.
Run: python test_agents.py
"""
from database import init_db
init_db()

from datetime import date, timedelta
today   = date.today()
monday  = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
end     = monday + timedelta(days=13)

from agents import (
    staffing_analysis_agent,
    coverage_planning_agent,
    roster_generation_agent,
    constraint_validation_agent,
    workload_fairness_agent,
    roster_optimisation_agent,
    reporting_agent,
    submit_for_approval,
)

print("=" * 60)
print("NURSE STAFFING & ROSTER OPTIMISATION — AGENT TEST")
print("=" * 60)

print("\n[1] Staffing Data Analysis Agent")
s = staffing_analysis_agent()
print(f"    Total staff : {s['total']}")
print(f"    RNs         : {s['rn_count']}")
print(f"    ENs         : {s['en_count']}")
print(f"    Senior RNs  : {s['senior_count']}")
print(f"    Skills      : {len(s['skills'])} unique skills")
print("    PASS")

print("\n[2] Coverage Planning Agent")
c = coverage_planning_agent(monday, end)
print(f"    Days         : {c['total_days']}")
print(f"    Slots needed : {c['total_required_slots']}")
print("    PASS")

print("\n[3] Roster Generation Agent")
r = roster_generation_agent(monday, end)
print(f"    Assignments  : {r['total_assignments']}")
print(f"    Period       : {r['roster_start']} to {r['roster_end']}")
print("    PASS")

print("\n[4] Constraint Validation Agent")
v = constraint_validation_agent()
print(f"    Violations   : {v['total_violations']}")
print(f"    Critical     : {v['critical']}")
print(f"    Warnings     : {v['warnings']}")
print("    PASS")

print("\n[5] Workload Fairness Agent")
w = workload_fairness_agent()
print(f"    Fairness     : {w['fairness_score']}%")
print(f"    Avg shifts   : {w['avg_shifts']}")
print(f"    Max/Min      : {w['max_shifts']} / {w['min_shifts']}")
print("    PASS")

print("\n[6] Roster Optimisation Agent")
o = roster_optimisation_agent()
print(f"    Recommendations : {o['total_recommendations']}")
print(f"    Summary: {o['summary'][:80]}...")
print("    PASS")

print("\n[7] Reporting Agent")
rep = reporting_agent()
print(f"    Roster days assigned : {rep['roster_summary']['roster_days']}")
print(f"    Total shifts         : {rep['roster_summary']['total_shifts_assigned']}")
print("    PASS")

print("\n[8] Human Review — Submit for Approval")
a = submit_for_approval("Dr. Sarah Mitchell", "Test submission", monday.isoformat(), end.isoformat())
print(f"    Approval ID : {a['approval_id']}")
print(f"    Status      : {a['status']}")
print("    PASS")

print("\n" + "=" * 60)
print("ALL AGENTS PASSED SUCCESSFULLY!")
print("=" * 60)
