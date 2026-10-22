#!/usr/bin/env python3
"""Track post-merge commits and selected authors on a monitored branch."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(PLUGIN_DIR, "state.json")
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            print(f"cannot read {path}: {exc}", file=sys.stderr)
    return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"cannot write {path}: {exc}", file=sys.stderr)


def repo_dir(payload, config):
    repo = payload.get("repo") or {}
    remote = repo.get("remoteUrl") or ""
    if remote and os.path.isdir(remote):
        return remote
    if repo.get("id"):
        mirrors = os.path.expanduser(config.get("mirrors_dir") or "~/.xissue/mirrors")
        candidate = os.path.join(mirrors, f"repo-{repo['id']}.git")
        if os.path.isdir(candidate):
            return candidate
    return None


def git(repo, args):
    if not repo:
        return ""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=8,
        )
        return result.stdout.strip()
    except Exception as exc:
        print(f"git {' '.join(args[:2])} failed: {exc}", file=sys.stderr)
        return ""


def normalize_author(value):
    return (value or "").strip().lstrip("@").lower()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"invalid stdin JSON: {exc}", file=sys.stderr)
        return 1

    event = payload.get("event")
    config = load_json(CONFIG_FILE, {
        "target_authors": ["release-bot", "ci-bot"],
        "max_post_merge_check": 3,
        "watch_files": ["package.json", "go.mod", "CHANGELOG.md", "VERSION"],
        "auto_create_issue_on_keyword": ["breaking", "rollback"],
        "mirrors_dir": "~/.xissue/mirrors",
    })
    state = load_json(STATE_FILE, {
        "last_merged": None,
        "post_merge_count": 0,
        "post_merge_branch": "",
    })
    actions = []
    changed = False

    if event == "pr_merged":
        pr = payload.get("pr") or {}
        project = payload.get("project") or {}
        state["last_merged"] = {
            "number": pr.get("number"),
            "title": pr.get("title"),
            "url": pr.get("url"),
            "author": pr.get("author"),
            "merged_at": datetime.now(timezone.utc).isoformat(),
        }
        state["post_merge_branch"] = pr.get("baseRefName") or project.get("targetBranch") or ""
        state["post_merge_count"] = 0
        changed = True
        actions.append({
            "type": "notify",
            "message": f"Recorded PR #{pr.get('number')} merge; watching the next "
                       f"{config.get('max_post_merge_check', 3)} commits on "
                       f"{state['post_merge_branch'] or 'the target branch'}.",
        })

    elif event == "branch_push":
        branch = payload.get("branch", "")
        commits = payload.get("commits") or []
        directory = repo_dir(payload, config)
        target_authors = {normalize_author(a) for a in config.get("target_authors", [])}
        watch_files = config.get("watch_files", [])
        max_after_merge = int(config.get("max_post_merge_check", 3))
        watching_branch = state.get("post_merge_branch", "")
        after_merge = (
            state.get("last_merged") is not None
            and state.get("post_merge_count", 0) < max_after_merge
            and (not watching_branch or branch == watching_branch)
        )

        for commit in commits:
            author = normalize_author(commit.get("author"))
            subject = commit.get("subject", "")
            sha = commit.get("sha", "")
            short = commit.get("shortSha") or sha[:7]
            count_after = 0

            if after_merge and state.get("post_merge_count", 0) < max_after_merge:
                state["post_merge_count"] = state.get("post_merge_count", 0) + 1
                count_after = state["post_merge_count"]
                changed = True

            if author not in target_authors and count_after == 0:
                continue

            files = [line.strip() for line in git(directory, [
                "show", "--name-only", "--pretty=format:", sha,
            ]).splitlines() if line.strip()]
            stat = git(directory, ["show", "--stat", "--oneline", sha])
            previews = []
            for watch in watch_files:
                if any(watch in name for name in files):
                    content = git(directory, ["show", f"{sha}:{watch}"])
                    if content:
                        snippet = "\n".join(content.splitlines()[:10])
                        previews.append(f"`{watch}`:\n```\n{snippet}\n```")

            reasons = []
            if count_after:
                merged = state.get("last_merged") or {}
                reasons.append(f"post-merge commit {count_after} for PR #{merged.get('number')}")
            if author in target_authors:
                reasons.append(f"author @{commit.get('author')}")

            lines = [
                f"Commit {short} by {commit.get('author')}",
                f"Reason: {', '.join(reasons)}",
                f"Subject: {subject}",
                f"Changed files: {len(files)}",
            ]
            if files:
                lines.append("Files: " + ", ".join(files[:8]))
            if stat:
                lines.append(stat[:1200])
            lines.extend(previews)
            actions.append({"type": "notify", "message": "\n".join(lines)})

            keywords = config.get("auto_create_issue_on_keyword", [])
            if any(keyword.lower() in subject.lower() for keyword in keywords):
                actions.append({
                    "type": "create_issue",
                    "prompt": f"Follow up on watched commit {short}: {subject}",
                })

    if changed:
        save_json(STATE_FILE, state)
    if actions:
        print(json.dumps({"actions": actions}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
