"""Generate synthetic identity, entitlement and badge data for a fictional company.

Every person, account and badge in this file is made up. The script plants a
realistic mix of access problems (terminated users who still have access,
dormant accounts, missing MFA and so on) so the review engine has something
to find.

Usage:
    python data/generate_data.py                 # writes CSVs into data/
    python data/generate_data.py --seed 7        # different random data
"""

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
REVIEW_DATE = date(2026, 10, 31)

FIRST = ["Ana", "Ben", "Carla", "Diego", "Elena", "Frank", "Grace", "Hector", "Iris", "Jamal",
         "Kara", "Luis", "Maya", "Nate", "Olivia", "Pedro", "Quinn", "Rosa", "Sam", "Tara",
         "Uriel", "Vera", "Will", "Ximena", "Yusuf", "Zoe"]
LAST = ["Alvarez", "Brooks", "Chen", "Diaz", "Evans", "Flores", "Garcia", "Hughes", "Ito",
        "Johnson", "Kim", "Lopez", "Martin", "Nguyen", "Ortiz", "Patel", "Reyes", "Smith",
        "Torres", "Vasquez", "Walker", "Young"]


def days_ago(n: int) -> date:
    return REVIEW_DATE - timedelta(days=n)


def build(seed: int, headcount: int = 160):
    rng = random.Random(seed)
    policy = json.loads((DATA_DIR / "policy.json").read_text())
    depts = policy["departments"]
    dept_names = list(depts)
    all_baseline = sorted({e for d in depts.values() for e in d["baseline"]})

    identities, accounts, entitlements, badges = [], [], [], []

    for i in range(headcount):
        uid = f"U{1001 + i}"
        dept = rng.choice(dept_names)
        first, last = rng.choice(FIRST), rng.choice(LAST)
        is_contractor = rng.random() < 0.18
        start = days_ago(rng.randint(120, 2200))

        status, term_date, end_date = "Active", "", ""
        if rng.random() < 0.12:
            status = "Terminated"
            term_date = days_ago(rng.randint(5, 200)).isoformat()
        if is_contractor:
            # most contracts end in the future; some have already ended
            end_date = (REVIEW_DATE + timedelta(days=rng.randint(-60, 240))).isoformat()

        identities.append({
            "user_id": uid,
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}{i}@lonestarbattery.example",
            "department": dept,
            "title": rng.choice(depts[dept]["titles"]),
            "employment_type": "Contractor" if is_contractor else "Employee",
            "hr_status": status,
            "start_date": start.isoformat(),
            "termination_date": term_date,
            "contract_end_date": end_date,
            "manager_id": f"U{1001 + rng.randint(0, 20)}",
        })

        # --- directory account -------------------------------------------
        enabled = True
        if status == "Terminated":
            enabled = rng.random() < 0.45          # plant: some never got disabled
        last_login = days_ago(rng.randint(0, 30))
        if rng.random() < 0.07:
            last_login = days_ago(rng.randint(95, 300))  # plant: dormant
        accounts.append({
            "user_id": uid,
            "account_enabled": str(enabled).lower(),
            "last_login": last_login.isoformat(),
            "mfa_enrolled": str(rng.random() > 0.08).lower(),
        })

        # --- entitlements -------------------------------------------------
        grants = list(depts[dept]["baseline"])
        if rng.random() < 0.08:                    # plant: access from another job
            grants.append(rng.choice([e for e in all_baseline if e not in grants]))
        if rng.random() < 0.06:                    # plant: unneeded admin rights
            grants.append(rng.choice(["Domain_Admin", "Firewall_Admin"]))
        if dept == "IT" and rng.random() < 0.5:
            grants.append("Domain_Admin")
        if dept == "Finance" and rng.random() < 0.15:
            grants.append("ERP_AP_Approve_Payment")  # plant: SoD conflict
        if dept == "Security" and rng.random() < 0.25:
            grants.append("Badge_Audit_Review")      # plant: SoD conflict
        if dept == "HR" and rng.random() < 0.2:
            grants.append("HRIS_Payroll_Admin")      # plant: SoD conflict
        for ent in dict.fromkeys(grants):
            certified = days_ago(rng.randint(10, 170))
            if rng.random() < 0.05:
                certified = days_ago(rng.randint(190, 400))  # plant: review overdue
            entitlements.append({
                "user_id": uid,
                "entitlement": ent,
                "granted_date": start.isoformat(),
                "last_certified": certified.isoformat(),
            })

        # --- physical badge -----------------------------------------------
        zones = list(depts[dept]["zones"])
        if rng.random() < 0.07:                    # plant: restricted zone not in role
            extra = [z for z in policy["restricted_zones"] if z not in zones]
            zones.append(rng.choice(extra))
        badge_active = True
        if status == "Terminated":
            badge_active = rng.random() < 0.35     # plant: badge still works
        badges.append({
            "badge_id": f"B{50000 + i}",
            "user_id": uid,
            "badge_status": "Active" if badge_active else "Disabled",
            "zones": ";".join(zones),
        })

    return identities, accounts, entitlements, badges


def write_csv(path: Path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--headcount", type=int, default=160)
    args = parser.parse_args()

    identities, accounts, entitlements, badges = build(args.seed, args.headcount)
    write_csv(DATA_DIR / "hr_roster.csv", identities)
    write_csv(DATA_DIR / "directory_accounts.csv", accounts)
    write_csv(DATA_DIR / "entitlements.csv", entitlements)
    write_csv(DATA_DIR / "badge_access.csv", badges)
    print(f"Wrote {len(identities)} identities, {len(entitlements)} entitlements "
          f"and {len(badges)} badges to {DATA_DIR}")


if __name__ == "__main__":
    main()
