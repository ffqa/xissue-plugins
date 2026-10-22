#!/usr/bin/env python3
"""Forward xIssue notifications to external channels.

Configuration lives next to this file in config.json:

{
  "macos_desktop": true,
  "feishu_webhook": "",
  "wecom_webhook": "",
  "dingtalk_webhook": "",
  "dingtalk_secret": "",
  "bark_url": ""
}
"""

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    defaults = {
        "macos_desktop": True,
        "feishu_webhook": "",
        "wecom_webhook": "",
        "dingtalk_webhook": "",
        "dingtalk_secret": "",
        "bark_url": "",
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as handle:
                defaults.update(json.load(handle))
        except Exception as exc:
            print(f"invalid config.json: {exc}", file=sys.stderr)
    return defaults


def post_json(url, payload):
    if not url:
        return
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status >= 300:
                print(f"webhook returned {response.status}", file=sys.stderr)
    except Exception as exc:
        print(f"webhook failed ({url.split('?')[0][:60]}): {exc}", file=sys.stderr)


def send_macos(title, body):
    if sys.platform != "darwin":
        return
    script = (
        "on run argv\n"
        "display notification (item 2 of argv) with title (item 1 of argv)\n"
        "end run"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script, title[:120], body.replace("\n", " ")[:180]],
            check=False,
            timeout=4,
        )
    except Exception as exc:
        print(f"macOS notification failed: {exc}", file=sys.stderr)


def send_feishu(url, title, body, link):
    text = f"{body}\n\n[查看详情]({link})" if link else body
    post_json(url, {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"🔔 {title}"}, "template": "blue"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}],
        },
    })


def send_wecom(url, title, body, link):
    markdown = f"### {title}\n\n{body}"
    if link:
        markdown += f"\n\n[查看详情]({link})"
    post_json(url, {"msg_type": "markdown", "markdown": {"content": markdown}})


def send_dingtalk(url, secret, title, body, link):
    text = f"### {title}\n\n{body}"
    if link:
        text += f"\n\n[查看详情]({link})"
    target = url
    if secret:
        timestamp = str(int(time.time() * 1000))
        sign_raw = f"{timestamp}\n{secret}".encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), sign_raw, hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(digest))
        separator = "&" if "?" in url else "?"
        target = f"{url}{separator}timestamp={timestamp}&sign={sign}"
    post_json(target, {"msgtype": "markdown", "markdown": {"title": title, "text": text}})


def send_bark(base_url, title, body, link):
    if not base_url:
        return
    url = f"{base_url.rstrip('/')}/{urllib.parse.quote(title)}/{urllib.parse.quote(body[:200])}"
    if link:
        url += f"?url={urllib.parse.quote(link, safe='')}"
    try:
        urllib.request.urlopen(url, timeout=5).close()
    except Exception as exc:
        print(f"Bark failed: {exc}", file=sys.stderr)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"invalid stdin JSON: {exc}", file=sys.stderr)
        return 1
    notification = payload.get("notification") or {}
    title = notification.get("title") or "xIssue 通知"
    body = notification.get("body") or ""
    link = notification.get("link") or ""
    config = load_config()

    if config.get("macos_desktop", True):
        send_macos(title, body)
    send_feishu(config.get("feishu_webhook", ""), title, body, link)
    send_wecom(config.get("wecom_webhook", ""), title, body, link)
    send_dingtalk(
        config.get("dingtalk_webhook", ""),
        config.get("dingtalk_secret", ""),
        title,
        body,
        link,
    )
    send_bark(config.get("bark_url", ""), title, body, link)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
