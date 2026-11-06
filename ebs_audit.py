#!/usr/bin/env python3
"""Report old unattached EBS volumes and write an optional deletion plan."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_time(value):
    """Parse the ISO timestamps returned by EC2."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def old_enough(created_at, cutoff):
    """Return true when a volume was created before the retention cutoff."""
    return parse_time(created_at) < cutoff


def make_record(account_id, account_name, region, volume, cutoff, rate):
    """Convert one EC2 volume into a report row, or return None when it is too new."""
    if volume.get("State") != "available":
        return None
    created_at = volume.get("CreateTime")
    if not created_at or not old_enough(created_at, cutoff):
        return None
    size_gib = int(volume.get("Size", 0))
    return {
        "account_id": account_id,
        "account_name": account_name,
        "region": region,
        "volume_id": volume["VolumeId"],
        "volume_type": volume.get("VolumeType", "unknown"),
        "size_gib": size_gib,
        "created_at": created_at,
        "estimated_monthly_cost_usd": round(size_gib * rate, 2),
    }


def build_report(accounts, older_than_days, rate, now=None):
    """Build a deterministic report from fixture-style account and volume data."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=older_than_days)
    rows = []
    for account in accounts:
        for volume in account.get("volumes", []):
            row = make_record(
                account["account_id"], account.get("account_name", "unknown"),
                account["region"], volume, cutoff, rate,
            )
            if row:
                rows.append(row)
    return {
        "generated_at": now.isoformat(),
        "older_than_days": older_than_days,
        "estimated_rate_usd_per_gib_month": rate,
        "volume_count": len(rows),
        "estimated_monthly_cost_usd": round(sum(r["estimated_monthly_cost_usd"] for r in rows), 2),
        "volumes": rows,
    }


def discover_accounts(org_client):
    """Return active Organizations accounts for the audit role to inspect."""
    accounts = []
    for page in org_client.get_paginator("list_accounts").paginate():
        accounts.extend(
            {"account_id": a["Id"], "account_name": a["Name"]}
            for a in page.get("Accounts", [])
            if a.get("Status") == "ACTIVE"
        )
    return accounts


def assume_role_session(sts_client, account_id, role_name, region):
    """Assume the read-only audit role in one member account."""
    import boto3

    result = sts_client.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/{role_name}",
        RoleSessionName="ebs-volume-audit",
    )
    credentials = result["Credentials"]
    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=region,
    )


def collect_live_accounts(profile, region, role_name):
    """Query Organizations and EC2 through a read-only cross-account role."""
    import boto3

    root_session = boto3.Session(profile_name=profile or None, region_name=region)
    org = root_session.client("organizations")
    sts = root_session.client("sts")
    results = []
    for account in discover_accounts(org):
        member_session = assume_role_session(sts, account["account_id"], role_name, region)
        ec2 = member_session.client("ec2", region_name=region)
        volumes = []
        for page in ec2.get_paginator("describe_volumes").paginate(
            Filters=[{"Name": "status", "Values": ["available"]}]
        ):
            volumes.extend(page.get("Volumes", []))
        results.append({**account, "region": region, "volumes": volumes})
    return results


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", type=Path, help="offline fixture JSON")
    source.add_argument("--live", action="store_true", help="query AWS Organizations and EC2")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile")
    parser.add_argument("--role-name", default="EbsAuditRole")
    parser.add_argument("--older-than-days", type=int, default=30)
    parser.add_argument("--rate", type=float, default=0.08, help="estimated USD per GiB-month")
    parser.add_argument("--output", type=Path, default=Path("ebs-report.json"))
    parser.add_argument("--deletion-plan", type=Path)
    args = parser.parse_args(argv)

    if args.older_than_days < 1 or args.rate < 0:
        parser.error("older-than-days must be positive and rate cannot be negative")
    try:
        if args.fixture:
            data = json.loads(args.fixture.read_text(encoding="utf-8"))
            accounts = data["accounts"]
        else:
            accounts = collect_live_accounts(args.profile, args.region, args.role_name)
        report = build_report(accounts, args.older_than_days, args.rate)
        write_json(args.output, report)
        if args.deletion_plan:
            write_json(args.deletion_plan, {
                "warning": "Review this list before deleting any volume.",
                "volumes": report["volumes"],
            })
    except (OSError, KeyError, TypeError, ValueError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"FOUND {report['volume_count']} old unattached volumes")
    print(f"ESTIMATED MONTHLY COST: ${report['estimated_monthly_cost_usd']:.2f}")
    print(f"REPORT: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

