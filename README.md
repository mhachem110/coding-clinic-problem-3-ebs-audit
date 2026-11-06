# Problem 3: Unattached EBS volume audit

## What it does

The Python tool finds old EBS volumes whose state is `available`, estimates their monthly storage cost, and writes a report. In live mode it lists active AWS Organizations accounts and assumes a read-only `EbsAuditRole` in each account. It never deletes a volume. An optional deletion plan is only a review list for a later, separately approved process.

## Files

- `ebs_audit.py`: offline fixture mode, live Organizations/STS/EC2 collection, report generation, and deletion-plan output.
- `fixtures/volumes.json`: dummy AWS-shaped data for a repeatable demo.
- `tests/test_ebs_audit.py`: verifies old unattached filtering and cost totals.
- `.gitignore`: excludes generated reports.

## Demo without AWS

```bash
python ebs_audit.py --fixture fixtures/volumes.json \
  --older-than-days 30 --output ebs-report.json \
  --deletion-plan deletion-plan.json
python -m unittest discover -s tests -v
```

The fixture contains two old unattached volumes and one attached volume. The report should find two volumes and estimate `$12.00` per month at the example rate of `$0.08` per GiB-month.

## Live mode

Install `boto3`, configure credentials that can list Organizations accounts, and grant the member-account role the minimum EC2 describe permissions. Then run:

```bash
python ebs_audit.py --live --region us-east-1 --role-name EbsAuditRole
```

Explain that the fixture proves the decision logic without making AWS calls; live mode swaps in Organizations, STS, and EC2 clients.

