#!/usr/bin/env python3
"""Forward xIssue notifications to a Slack incoming webhook."""

import json
import os
import sys
import urllib.request

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    config = {"webhook_url": "", "base_url": ""}
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
    webhook = config.get("webhook_url") or os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        print("webhook_url is not configured", file=sys.stderr)
        return 1

    notification = payload.get("notification") or {}
    title = notification.get("title") or "xIssue"
    body = notification.get("body") or ""
    link = notification.get("link") or ""
    if link.startswith("/") and config.get("base_url"):
        link = config["base_url"].rstrip("/") + link

    text = f"*{title}*\n{body}"
    if link:
        text += f"\n<{link}|Open in xIssue>"
    request = urllib.request.Request(
        webhook,
        data=json.dumps({"text": text, "mrkdwn": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=5).close()
    except Exception as exc:
        print(f"slack webhook failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
