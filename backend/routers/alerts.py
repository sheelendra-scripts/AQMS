"""Alerts API — threshold-based AQI alert rules and history."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["alerts"])

# ── In-memory stores ─────────────────────────────────
ALERT_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "rule_default_severe",
        "name": "Severe AQI Alert",
        "description": "Alert when AQI exceeds 400 (Severe)",
        "metric": "aqi",
        "threshold": 400,
        "operator": "gt",
        "zone": "all",
        "severity": "critical",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "rule_id": "rule_default_very_poor",
        "name": "Very Poor AQI Alert",
        "description": "Alert when AQI exceeds 300 (Very Poor)",
        "metric": "aqi",
        "threshold": 300,
        "operator": "gt",
        "zone": "all",
        "severity": "critical",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "rule_id": "rule_default_poor",
        "name": "Poor AQI Warning",
        "description": "Alert when AQI exceeds 200 (Poor)",
        "metric": "aqi",
        "threshold": 200,
        "operator": "gt",
        "zone": "all",
        "severity": "warning",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "rule_id": "rule_default_moderate",
        "name": "Moderate AQI Notice",
        "description": "Alert when AQI exceeds 150",
        "metric": "aqi",
        "threshold": 150,
        "operator": "gt",
        "zone": "all",
        "severity": "info",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "rule_id": "rule_default_pm25",
        "name": "High PM2.5",
        "description": "Alert when PM2.5 exceeds 120 µg/m³ (Unhealthy)",
        "metric": "pm25",
        "threshold": 120,
        "operator": "gt",
        "zone": "all",
        "severity": "warning",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "rule_id": "rule_default_pm25_severe",
        "name": "Severe PM2.5",
        "description": "Alert when PM2.5 exceeds 250 µg/m³ (Hazardous)",
        "metric": "pm25",
        "threshold": 250,
        "operator": "gt",
        "zone": "all",
        "severity": "critical",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "rule_id": "rule_default_co",
        "name": "High CO Level",
        "description": "Alert when CO exceeds 6.0 mg/m³",
        "metric": "co",
        "threshold": 6.0,
        "operator": "gt",
        "zone": "all",
        "severity": "critical",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    },
]

ALERT_HISTORY: List[Dict[str, Any]] = []
MAX_HISTORY = 200

# Debounce: track last fire time per (rule_id, ward_id) — 5 min cooldown
_recent_fires: Dict[str, str] = {}
DEBOUNCE_SECONDS = 300


def evaluate_rules(ward_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check ward data against all enabled rules. Returns list of newly triggered alerts."""
    triggered = []
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")

    for rule in ALERT_RULES:
        if not rule["enabled"]:
            continue

        metric    = rule["metric"]
        threshold = float(rule["threshold"])
        op        = rule["operator"]
        target    = rule["zone"]

        for ward in ward_data:
            # Zone filter
            if target != "all":
                if ward.get("name") != target and ward.get("ward_id") != target:
                    continue

            value = ward.get(metric)
            if value is None:
                continue

            fired = (
                (op == "gt" and float(value) > threshold) or
                (op == "lt" and float(value) < threshold) or
                (op == "eq" and float(value) == threshold)
            )
            if not fired:
                continue

            # Debounce
            fire_key = f"{rule['rule_id']}_{ward['ward_id']}"
            last_fire = _recent_fires.get(fire_key)
            if last_fire:
                last_dt = datetime.fromisoformat(last_fire.replace("Z", "+00:00"))
                if (now - last_dt).total_seconds() < DEBOUNCE_SECONDS:
                    continue

            alert = {
                "alert_id":  str(uuid.uuid4())[:8],
                "rule_id":   rule["rule_id"],
                "rule_name": rule["name"],
                "zone":      ward.get("name", ward["ward_id"]),
                "ward_id":   ward["ward_id"],
                "metric":    metric,
                "value":     round(float(value), 2),
                "threshold": threshold,
                "severity":  rule["severity"],
                "message":   f"{ward.get('name', ward['ward_id'])}: {metric.upper()} = {round(float(value),1)} (>{threshold})",
                "timestamp": now_iso,
            }
            triggered.append(alert)
            _recent_fires[fire_key] = now_iso

    # Prepend to history, cap size
    ALERT_HISTORY[:0] = triggered
    del ALERT_HISTORY[MAX_HISTORY:]

    return triggered


# ── Endpoints ─────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(limit: int = 50):
    """Return recent alert history."""
    return {
        "count":  len(ALERT_HISTORY),
        "alerts": ALERT_HISTORY[:limit],
    }


@router.get("/alerts/stats")
async def get_alert_stats():
    """Summary stats for alert dashboard."""
    critical = sum(1 for a in ALERT_HISTORY if a.get("severity") == "critical")
    warning  = sum(1 for a in ALERT_HISTORY if a.get("severity") == "warning")
    zones    = list({a["zone"] for a in ALERT_HISTORY})
    return {
        "total":         len(ALERT_HISTORY),
        "critical":      critical,
        "warning":       warning,
        "affected_zones": zones,
        "active_rules":  sum(1 for r in ALERT_RULES if r["enabled"]),
    }


@router.get("/alerts/rules")
async def get_rules():
    """Return all alert rules."""
    return {"count": len(ALERT_RULES), "rules": ALERT_RULES}


@router.post("/alerts/rules")
async def create_rule(rule: dict):
    """Create a new alert rule."""
    new_rule = {
        "rule_id":     f"rule_{str(uuid.uuid4())[:8]}",
        "name":        rule.get("name", "Unnamed Rule"),
        "description": rule.get("description", ""),
        "metric":      rule.get("metric", "aqi"),
        "threshold":   float(rule.get("threshold", 200)),
        "operator":    rule.get("operator", "gt"),
        "zone":        rule.get("zone", "all"),
        "severity":    rule.get("severity", "warning"),
        "enabled":     rule.get("enabled", True),
        "created_at":  datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    ALERT_RULES.append(new_rule)
    return new_rule


@router.put("/alerts/rules/{rule_id}")
async def update_rule(rule_id: str, updates: dict):
    """Toggle or update an alert rule."""
    for rule in ALERT_RULES:
        if rule["rule_id"] == rule_id:
            rule.update({k: v for k, v in updates.items() if k != "rule_id"})
            return rule
    return {"error": "Rule not found"}


@router.delete("/alerts/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete an alert rule."""
    before = len(ALERT_RULES)
    ALERT_RULES[:] = [r for r in ALERT_RULES if r["rule_id"] != rule_id]
    return {"deleted": rule_id, "removed": before - len(ALERT_RULES)}


@router.delete("/alerts")
async def clear_alert_history():
    """Clear alert history."""
    ALERT_HISTORY.clear()
    _recent_fires.clear()
    return {"cleared": True}
