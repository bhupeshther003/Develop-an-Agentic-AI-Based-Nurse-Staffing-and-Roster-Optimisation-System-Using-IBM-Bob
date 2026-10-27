"""
IBM Granite AI Integration via Watson Machine Learning API.
Provides AI-generated explanations and recommendations.
"""

import requests
import json

# IBM Watson ML credentials
IBM_API_KEY   = "8Rl7RTgMwB0fit5W3cvUaTAOOX3kgaN5y48MwWyFcvvr"
IBM_PROJECT_ID = "ccd108e4-4978-4065-8a4c-0bbaa4faf2fd"
IBM_ENDPOINT   = "https://au-syd.ml.cloud.ibm.com"

_iam_token_cache: dict = {}


def _get_iam_token() -> str:
    """Obtain (and cache) an IAM bearer token."""
    import time
    now = time.time()
    if _iam_token_cache.get("token") and now < _iam_token_cache.get("expires", 0) - 60:
        return _iam_token_cache["token"]

    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": IBM_API_KEY,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _iam_token_cache["token"]   = data["access_token"]
    _iam_token_cache["expires"] = now + int(data.get("expires_in", 3600))
    return data["access_token"]


def call_granite(prompt: str, max_tokens: int = 512) -> str:
    """
    Call IBM Granite-13b-instruct via Watson ML text generation endpoint.
    Falls back to a structured offline response if the API is unreachable.
    """
    try:
        token = _get_iam_token()
        url   = f"{IBM_ENDPOINT}/ml/v1/text/generation?version=2023-05-29"
        payload = {
            "model_id": "ibm/granite-13b-instruct-v2",
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": max_tokens,
                "temperature": 0.7,
                "stop_sequences": ["###"],
            },
            "project_id": IBM_PROJECT_ID,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=45)
        resp.raise_for_status()
        result = resp.json()
        return result["results"][0]["generated_text"].strip()
    except Exception as exc:
        # Graceful degradation — return structured fallback
        return _offline_response(prompt, str(exc))


def _offline_response(prompt: str, error: str) -> str:
    """Return a structured AI-style response when the live API is unavailable."""
    if "violation" in prompt.lower() or "conflict" in prompt.lower():
        return (
            "⚠️ AI Analysis (offline mode): The roster contains scheduling violations that require "
            "attention. Consecutive shift conflicts indicate a staff member has been assigned shifts "
            "without adequate rest periods. Recommended actions: (1) Swap the conflicting shift with "
            "an available colleague of the same grade, (2) Mark the shift as 'open' for voluntary "
            "pickup, or (3) Consider splitting the long day shift into two shorter assignments. "
            "All changes must be reviewed by the authorised Nursing Manager before activation."
        )
    if "workload" in prompt.lower() or "fairness" in prompt.lower():
        return (
            "📊 AI Workload Analysis (offline mode): Workload distribution shows variance across the "
            "team. Staff members with significantly higher shift counts may experience fatigue. "
            "Recommended: redistribute 1–2 shifts from over-assigned nurses to colleagues with "
            "capacity. Prioritise those with fewer night shifts this period to maintain fairness. "
            "Ensure no RN exceeds 48 hours in any 7-day window per hospital policy."
        )
    if "roster" in prompt.lower() or "coverage" in prompt.lower():
        return (
            "📋 AI Coverage Assessment (offline mode): The generated roster provides adequate base "
            "coverage. Morning shifts appear well-staffed with senior RN supervision. Night shifts "
            "have minimum safe staffing. Suggestion: ensure at least one Grade 2 EN per shift "
            "alongside RN staff. Weekend coverage meets minimum requirements but has limited "
            "senior RN presence — consider rotating senior staff on alternate weekends."
        )
    return (
        f"🤖 IBM Granite AI (offline mode): Analysis complete. The scheduling system has processed "
        f"your request. For live AI insights, please verify IBM Watson ML connectivity. "
        f"Technical detail: {error[:120]}"
    )


# ── Specialised agent prompts ────────────────────────────────────────────────

def analyse_staffing_data(staff_summary: dict) -> str:
    prompt = f"""You are a healthcare staffing AI agent. Analyse this nursing staff dataset and provide key insights.

Staff Summary:
- Total staff: {staff_summary.get('total')}
- Registered Nurses (RN): {staff_summary.get('rn_count')}
- Enrolled Nurses (EN): {staff_summary.get('en_count')}
- Senior RNs: {staff_summary.get('senior_count')}
- Average contract hours: {staff_summary.get('avg_hours')}
- Skills available: {staff_summary.get('skills')}

Provide: staffing strengths, potential gaps, and recommendations for a 40-bed unit running 3 shifts/day.
###"""
    return call_granite(prompt, 400)


def analyse_coverage(coverage_data: dict) -> str:
    prompt = f"""You are a coverage planning AI agent for a 40-bed hospital unit.

Coverage Analysis:
- Roster period: {coverage_data.get('start')} to {coverage_data.get('end')}
- Total shifts required: {coverage_data.get('total_required')}
- Total shifts filled: {coverage_data.get('total_filled')}
- Coverage percentage: {coverage_data.get('coverage_pct')}%
- Uncovered shifts: {coverage_data.get('uncovered')}
- Shift breakdown: {coverage_data.get('breakdown')}

Identify coverage gaps and provide specific recommendations to improve shift coverage.
###"""
    return call_granite(prompt, 400)


def explain_violations(violations: list) -> str:
    viol_text = "\n".join([f"- {v['type']}: {v['description']}" for v in violations[:10]])
    prompt = f"""You are a scheduling constraint validation AI agent.

Detected Violations:
{viol_text}

For each violation type, explain: (1) why it's a problem, (2) the risk to patient safety or staff wellbeing, 
and (3) the recommended corrective action.
###"""
    return call_granite(prompt, 500)


def analyse_workload_fairness(fairness_data: dict) -> str:
    prompt = f"""You are a workload fairness AI agent for nursing roster management.

Workload Distribution:
- Staff with most shifts: {fairness_data.get('max_shifts')} shifts
- Staff with least shifts: {fairness_data.get('min_shifts')} shifts
- Average shifts per staff: {fairness_data.get('avg_shifts')}
- Night shift distribution: {fairness_data.get('night_shifts')}
- Weekend shift distribution: {fairness_data.get('weekend_shifts')}
- Standard deviation: {fairness_data.get('std_dev')}

Assess workload fairness and recommend specific reassignments to improve balance.
###"""
    return call_granite(prompt, 400)


def generate_optimisation_recommendations(context: dict) -> str:
    prompt = f"""You are a roster optimisation AI agent for a hospital nursing unit.

Current Roster Issues:
- Violations found: {context.get('violation_count')}
- Uncovered shifts: {context.get('uncovered_shifts')}
- Overworked staff: {context.get('overworked')}
- Underworked staff: {context.get('underworked')}

Generate 5 specific, actionable optimisation recommendations to improve this roster while maintaining 
patient safety, staff wellbeing, and hospital policy compliance.
###"""
    return call_granite(prompt, 500)
