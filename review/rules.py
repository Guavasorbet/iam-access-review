"""Access review rules.

Each rule looks at one person's combined record (HR status, directory account,
entitlements and badge) and returns zero or more findings. Rules are mapped to
NIST SP 800-53 controls so every finding points to the requirement it breaks.
"""

from dataclasses import dataclass, asdict
from datetime import date

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


@dataclass
class Rule:
    rule_id: str
    name: str
    severity: str
    control: str
    action: str


RULES = {
    "AR-01": Rule("AR-01", "Terminated user still has an enabled account", "Critical",
                  "AC-2(3) Disable Accounts", "Disable the account today and confirm with HR."),
    "AR-02": Rule("AR-02", "Terminated user still has an active badge", "Critical",
                  "PE-2 Physical Access Authorizations", "Deactivate the badge and recover the card."),
    "AR-03": Rule("AR-03", "Contractor past contract end still has access", "High",
                  "AC-2(2) Temporary Account Management", "Disable access or get the sponsor to extend the contract."),
    "AR-04": Rule("AR-04", "Privileged access without MFA", "High",
                  "IA-2(1) MFA for Privileged Accounts", "Enroll MFA before the next login, or remove the privilege."),
    "AR-05": Rule("AR-05", "Separation of duties conflict", "High",
                  "AC-5 Separation of Duties", "Remove one of the two entitlements or document a compensating control."),
    "AR-06": Rule("AR-06", "Badge opens a restricted zone outside the role", "High",
                  "PE-3 Physical Access Control", "Remove the zone unless the manager approves a business need."),
    "AR-07": Rule("AR-07", "Entitlement outside the role baseline", "Medium",
                  "AC-6 Least Privilege", "Ask the manager to justify the access or remove it."),
    "AR-08": Rule("AR-08", "Dormant account (no login in 90+ days)", "Medium",
                  "AC-2(3) Disable Accounts", "Confirm with the manager, then disable if unused."),
    "AR-09": Rule("AR-09", "Access not certified in 180+ days", "Low",
                  "AC-2 Account Management (periodic review)", "Send to the manager for certification."),
}


def _d(value: str):
    return date.fromisoformat(value) if value else None


def evaluate_person(person: dict, policy: dict, review_date: date) -> list[dict]:
    """Return the findings for one person.

    `person` holds: identity (dict), account (dict), entitlements (list of
    dicts) and badge (dict or None).
    """
    ident, acct, ents, badge = person["identity"], person["account"], person["entitlements"], person["badge"]
    dept = policy["departments"][ident["department"]]
    names = {e["entitlement"] for e in ents}
    enabled = acct["account_enabled"] == "true"
    badge_active = bool(badge) and badge["badge_status"] == "Active"
    terminated = ident["hr_status"] == "Terminated"
    findings = []

    def add(rule_id, detail):
        rule = RULES[rule_id]
        findings.append({**asdict(rule), "rule": rule.name, "detail": detail,
                         "user_id": ident["user_id"], "name": ident["name"],
                         "department": ident["department"], "title": ident["title"],
                         "employment_type": ident["employment_type"]})

    # AR-01 / AR-02: leavers who kept access
    if terminated and enabled:
        add("AR-01", f"Terminated {ident['termination_date']}; account still enabled.")
    if terminated and badge_active:
        add("AR-02", f"Terminated {ident['termination_date']}; badge {badge['badge_id']} still active.")

    # AR-03: contractors past their end date
    end = _d(ident["contract_end_date"])
    if ident["employment_type"] == "Contractor" and end and end < review_date and not terminated:
        if enabled or badge_active:
            what = " and ".join(x for x, on in (("account", enabled), ("badge", badge_active)) if on)
            add("AR-03", f"Contract ended {end.isoformat()}; {what} still active.")

    # AR-04: privileged rights without MFA
    privileged = sorted(names & set(policy["privileged_entitlements"]))
    if enabled and privileged and acct["mfa_enrolled"] != "true":
        add("AR-04", f"Holds {', '.join(privileged)} with no MFA enrolled.")

    # AR-05: toxic combinations
    for pair in policy["sod_conflicts"]:
        if pair["a"] in names and pair["b"] in names:
            add("AR-05", f"Has both {pair['a']} and {pair['b']}. {pair['why']}")

    # AR-06: restricted physical zones not in the role's badge profile
    if badge_active and not terminated:
        zones = set(badge["zones"].split(";"))
        extra = sorted((zones - set(dept["zones"])) & set(policy["restricted_zones"]))
        if extra:
            add("AR-06", f"Badge opens {', '.join(extra)}, not part of the {ident['department']} profile.")

    # AR-07: least privilege
    allowed = set(dept["baseline"]) | set(dept.get("allowed_additional", []))
    outside = sorted(names - allowed)
    if outside and not terminated:
        add("AR-07", f"Has {', '.join(outside)}, outside the {ident['department']} baseline.")

    # AR-08: dormant accounts (active people only; leavers are AR-01)
    last_login = _d(acct["last_login"])
    if enabled and not terminated and last_login:
        idle = (review_date - last_login).days
        if idle >= policy["dormant_days"]:
            add("AR-08", f"Last login {last_login.isoformat()} ({idle} days ago).")

    # AR-09: certification overdue
    if not terminated:
        stale = [e for e in ents
                 if (review_date - _d(e["last_certified"])).days > policy["certification_max_days"]]
        if stale:
            oldest = min(_d(e["last_certified"]) for e in stale)
            add("AR-09", f"{len(stale)} entitlement(s) not certified since {oldest.isoformat()}.")

    return findings
