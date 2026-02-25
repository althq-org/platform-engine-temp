"""Preflight — Agent Factory infrastructure verification.

Runs inside the VPC with sg_agents. If Preflight passes, agents will too.
Exit 0 = all checks passed. Exit 1 = something is broken.
"""

import json
import os
import socket
import sys
import time
from pathlib import Path

RESULTS: list[dict] = []


def check(name: str, fn, retries: int = 3, backoff: int = 5) -> None:
    for attempt in range(retries):
        try:
            fn()
            RESULTS.append({"check": name, "status": "PASS"})
            return
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
            else:
                RESULTS.append({"check": name, "status": "FAIL", "error": str(e)})


def verify_efs() -> None:
    probe = Path("/mnt/efs/.preflight-probe")
    probe.write_text("ok")
    assert probe.read_text() == "ok", "Read-back mismatch"
    probe.unlink()


def verify_redis() -> None:
    import redis as r

    c = r.Redis(
        host=os.environ["REDIS_HOST"], port=6379, decode_responses=True,
    )
    assert c.ping(), "Redis ping failed"
    c.set("__preflight__", "ok", ex=10)
    assert c.get("__preflight__") == "ok", "Redis GET mismatch"


def verify_rds() -> None:
    import psycopg2

    conn = psycopg2.connect(
        host=os.environ["RDS_HOST"],
        port=5432,
        user=os.environ["RDS_USER"],
        password=os.environ["RDS_PASSWORD"],
        dbname=os.environ.get("RDS_DB", "postgres"),
    )
    cur = conn.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone()[0] == 1, "SELECT 1 returned unexpected result"
    conn.close()


def verify_cloudmap() -> None:
    result = socket.getaddrinfo("dispatcher.agents.local", 8000)
    assert len(result) > 0, "Cloud Map DNS returned no results"


def verify_outbound() -> None:
    import httpx

    resp = httpx.get("https://github.com", timeout=10, follow_redirects=True)
    assert resp.status_code == 200, f"GitHub returned {resp.status_code}"


if __name__ == "__main__":
    check("EFS mount + read/write", verify_efs)
    check("Redis ping + SET/GET", verify_redis)
    check("RDS connect + SELECT 1", verify_rds)
    check("Cloud Map DNS resolution", verify_cloudmap)
    check("Outbound internet (github.com)", verify_outbound)

    for r in RESULTS:
        print(json.dumps(r))

    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    if failed:
        print(f"\n{len(failed)} check(s) FAILED")
        sys.exit(1)
    print(f"\nAll {len(RESULTS)} checks PASSED")
