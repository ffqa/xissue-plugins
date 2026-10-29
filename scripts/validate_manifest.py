#!/usr/bin/env python3
"""Validate xIssue plugin manifests without requiring xIssue."""

import json
import os
import re
import sys

import yaml

EVENTS = {
    "branch_push",
    "pr_merged",
    "pr_created",
    "pr_comment",
    "pr_review",
    "notification_dispatch",
    "issue_created",
    "issue_status_changed",
    "run_started",
    "run_finished",
    "all",
    "*",
}
PERMISSIONS = {"repo:read", "repo:write", "network", "notify", "process"}
UI_SLOTS = {"project.page", "project.header", "project.toolbar", "issue.page", "issue.actions", "issue.toolbar"}
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def fail(message):
    print(f"invalid: {message}", file=sys.stderr)
    return 1


def main():
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    path = os.path.join(directory, "plugin.yaml")
    if not os.path.isfile(path):
        return fail(f"missing {path}")
    with open(path, encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict):
        return fail("manifest must be a mapping")
    if manifest.get("apiVersion") != 1:
        return fail("apiVersion must be 1")
    if not NAME.match(str(manifest.get("name", ""))):
        return fail("invalid name")
    if not manifest.get("version"):
        return fail("version is required")
    entrypoint = manifest.get("entrypoint")
    if not entrypoint or os.path.isabs(entrypoint) or ".." in entrypoint.split("/"):
        return fail("invalid entrypoint")
    if not os.path.isfile(os.path.join(directory, entrypoint)):
        return fail(f"missing entrypoint {entrypoint}")
    events = manifest.get("events")
    if not isinstance(events, list) or not events:
        return fail("events must be non-empty")
    unknown = [event for event in events if event not in EVENTS]
    if unknown:
        return fail(f"unknown events: {unknown}")
    permissions = manifest.get("permissions", [])
    unknown_permissions = [perm for perm in permissions if perm not in PERMISSIONS]
    if unknown_permissions:
        return fail(f"unknown permissions: {unknown_permissions}")
    ui = manifest.get("ui")
    if ui is not None:
        if not isinstance(ui, dict):
            return fail("ui must be a mapping")
        ui_entry = ui.get("entry")
        if not isinstance(ui_entry, str):
            return fail("ui.entry must be a string")
        ui_entry = ui_entry.replace("\\", "/")
        if os.path.isabs(ui_entry) or ".." in ui_entry.split("/") or not ui_entry.startswith("ui/"):
            return fail("ui.entry must be a relative path under ui/")
        if not os.path.isfile(os.path.join(directory, ui_entry)):
            return fail(f"missing ui.entry {ui_entry}")
        slots = ui.get("slots", [])
        if not isinstance(slots, list):
            return fail("ui.slots must be a list")
        unknown_slots = [slot for slot in slots if slot not in UI_SLOTS]
        if unknown_slots:
            return fail(f"unknown ui slots: {unknown_slots}")
    print(json.dumps({"ok": True, "plugin": manifest["name"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
