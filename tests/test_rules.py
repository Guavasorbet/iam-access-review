"""Unit tests for the access review rules. Run with: python -m unittest discover tests"""

import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "review"))
from rules import evaluate_person  # noqa: E402

POLICY = json.loads((ROOT / "data" / "policy.json").read_text())
REVIEW = date(2026, 10, 31)


def person(dept="Production", hr="Active", enabled="true", mfa="true", last_login="2026-10-20",
           ents=None, badge_status="Active", zones=None, emp="Employee", contract_end="",
           certified="2026-09-01"):
    d = POLICY["departments"][dept]
    ents = ents if ents is not None else d["baseline"]
    return {
        "identity": {"user_id": "U9999", "name": "Test User", "department": dept, "title": d["titles"][0],
                     "employment_type": emp, "hr_status": hr,
                     "termination_date": "2026-09-01" if hr == "Terminated" else "",
                     "contract_end_date": contract_end},
        "account": {"account_enabled": enabled, "last_login": last_login, "mfa_enrolled": mfa},
        "entitlements": [{"entitlement": e, "last_certified": certified} for e in ents],
        "badge": {"badge_id": "B1", "badge_status": badge_status,
                  "zones": ";".join(zones if zones is not None else d["zones"])},
    }


def rule_ids(p):
    return sorted({f["rule_id"] for f in evaluate_person(p, POLICY, REVIEW)})


class TestRules(unittest.TestCase):
    def test_clean_person_has_no_findings(self):
        self.assertEqual(rule_ids(person()), [])

    def test_terminated_with_account_and_badge(self):
        self.assertEqual(rule_ids(person(hr="Terminated")), ["AR-01", "AR-02"])

    def test_terminated_fully_deprovisioned_is_clean(self):
        self.assertEqual(rule_ids(person(hr="Terminated", enabled="false", badge_status="Disabled")), [])

    def test_expired_contractor(self):
        self.assertIn("AR-03", rule_ids(person(emp="Contractor", contract_end="2026-10-01")))

    def test_active_contractor_is_clean(self):
        self.assertEqual(rule_ids(person(emp="Contractor", contract_end="2027-03-01")), [])

    def test_privileged_without_mfa(self):
        p = person(dept="IT", ents=["ServiceDesk_Agent", "Email", "Domain_Admin"], mfa="false")
        self.assertIn("AR-04", rule_ids(p))

    def test_sod_conflict(self):
        p = person(dept="Finance", ents=["ERP_AP_Create_Vendor", "ERP_AP_Approve_Payment", "Email"])
        self.assertIn("AR-05", rule_ids(p))

    def test_restricted_zone_outside_role(self):
        zones = POLICY["departments"]["Production"]["zones"] + ["Server Room"]
        self.assertEqual(rule_ids(person(zones=zones)), ["AR-06"])

    def test_entitlement_outside_baseline(self):
        ents = POLICY["departments"]["Production"]["baseline"] + ["WMS_Inventory"]
        self.assertEqual(rule_ids(person(ents=ents)), ["AR-07"])

    def test_dormant_account(self):
        self.assertEqual(rule_ids(person(last_login="2026-06-01")), ["AR-08"])

    def test_certification_overdue(self):
        self.assertEqual(rule_ids(person(certified="2026-01-15")), ["AR-09"])


if __name__ == "__main__":
    unittest.main()
