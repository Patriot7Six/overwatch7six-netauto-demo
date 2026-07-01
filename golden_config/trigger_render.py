"""Trigger the RenderGoldenConfig Nautobot Job and wait for it to finish.

CLI entry point for `make render`. Looks up the job by name, enables it if
this is the first run (newly discovered Nautobot jobs are disabled by
default), starts it, and polls the JobResult until it finishes.

Nautobot Jobs API reference:
  https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/jobs/
"""

from __future__ import annotations

import os
import sys
import time

import httpx

JOB_NAME = "Render Golden Config"
POLL_INTERVAL_SECONDS = 2
TIMEOUT_SECONDS = 120

# Celery task states (JobResult.status mirrors these): only these three are
# terminal. Everything else (PENDING, RECEIVED, STARTED, RETRY) means the
# job is still in flight and polling should continue.
TERMINAL_STATUSES = {"SUCCESS", "FAILURE", "REVOKED"}


def main() -> None:
    url = os.getenv("NAUTOBOT_URL", "http://localhost:8080")
    token = os.getenv("NAUTOBOT_TOKEN", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    client = httpx.Client(
        base_url=url,
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
        timeout=30,
    )

    jobs = client.get("/api/extras/jobs/", params={"name": JOB_NAME}).json()["results"]
    if not jobs:
        print(f"ERROR: '{JOB_NAME}' job not found — is nautobot/jobs mounted?", file=sys.stderr)
        sys.exit(1)
    job = jobs[0]

    if not job["enabled"]:
        client.patch(f"/api/extras/jobs/{job['id']}/", json={"enabled": True}).raise_for_status()

    run_resp = client.post(
        f"/api/extras/jobs/{job['id']}/run/", json={"data": {}}, timeout=30
    )
    run_resp.raise_for_status()
    run = run_resp.json()
    result_url = run["job_result"]["url"] if "job_result" in run else run["url"]

    deadline = time.time() + TIMEOUT_SECONDS
    result: dict = {}
    while time.time() < deadline:
        result = client.get(result_url).json()
        status = result["status"]["value"]
        if status in TERMINAL_STATUSES:
            break
        time.sleep(POLL_INTERVAL_SECONDS)
    else:
        print(f"ERROR: job did not finish within {TIMEOUT_SECONDS}s", file=sys.stderr)
        sys.exit(1)

    status = result["status"]["value"]
    print(f"{status}: {result.get('result') or ''}")
    if status != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
