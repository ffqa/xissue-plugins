#!/usr/bin/env python3
"""Append run lifecycle events to a JSONL audit log."""

import json
import os
import sys
from datetime import datetime, timezone

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")


def load_config():
    config = {"log_file": "audit.jsonl", "notify_on_failure": True}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as handle:
                config.update(json.load(handle))
        except Exception as exc:
            print(f"invalid config.json: {exc}", file=sys.stderr)
    return config


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"invalid stdin JSON: {exc}", file=sys.stderr)
        return 1

    config = load_config()
    log_file = config.get("log_file") or "audit.jsonl"
    if not os.path.isabs(log_file):
        log_file = os.path.join(PLUGIN_DIR, log_file)

    record = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "event": payload.get("event"),
        "project": (payload.get("project") or {}).get("name"),
        "issue": (payload.get("issue") or {}).get("key"),
        "run_id": (payload.get("run") or {}).get("id"),
        "status": (payload.get("run") or {}).get("status"),
        "agent": (payload.get("run") or {}).get("agent"),
    }
    try:
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"cannot write audit log: {exc}", file=sys.stderr)
        return 1

    run = payload.get("run") or {}
    if (
        payload.get("event") == "run_finished"
        and config.get("notify_on_failure", True)
        and run.get("status") == "failed"
    ):
        print(json.dumps({
            "actions": [{
                "type": "notify",
                "message": f"Run #{run.get('id')} failed for {record['issue']}: {run.get('error', 'no error message')}",
            }],
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
