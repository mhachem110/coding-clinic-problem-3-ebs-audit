# Problem 3: Unattached EBS volume audit

## What it does

The Python tool finds old EBS volumes whose state is `available`, estimates their monthly storage cost, and writes a report. In live mode it lists active AWS Organizations accounts and assumes a read-only `EbsAuditRole` in each account. It never deletes a volume. An optional deletion plan is only a review list for a later, separately approved process.

See [`DESIGN.md`](DESIGN.md) for the account flow, filtering rules, and safety boundary.

## Files

- `ebs_audit.py`: offline fixture mode, live Organizations/STS/EC2 collection, report generation, and deletion-plan output.
- `fixtures/volumes.json`: dummy AWS-shaped data for a repeatable demo. It has two accounts, each with a region and a list of volumes. Each volume has an ID, state, size in GiB, type, and creation time. The `available` entries are unattached; the `in-use` entry is attached and should be excluded.
- `tests/test_ebs_audit.py`: verifies old unattached filtering and cost totals.
- `.github/workflows/ci.yml`: runs the test and offline demo automatically on pushes and pull requests.
- `.gitignore`: excludes Python cache files and the generated report and review list.

### How the files fit together

1. The demo command reads `fixtures/volumes.json`.
2. `ebs_audit.py` keeps volumes that are `available` and whose **creation date** is older than the age threshold.
3. It estimates monthly cost as size in GiB multiplied by the selected rate.
   The JSON report includes a note that this flat-rate estimate can differ from AWS pricing by volume type and region.
4. It writes a report and, if requested, a review list. It does not delete volumes.
5. The test checks that the attached volume is excluded and that the two matching volumes total `$12.00` at the example rate.

The fixture is JSON, so it cannot contain comments without becoming invalid input. Its fields are explained here instead.

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

