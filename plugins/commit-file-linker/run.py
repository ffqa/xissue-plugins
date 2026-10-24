#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xIssue 插件: commit-file-linker (提交文件直达插件)
核心触发逻辑：
必须同时满足以下三个条件（三者皆为 True，缺一即为 False）：
1. Branch 命中：当前推送分支必须匹配规则指定的 branch (支持单个或多个，如 "dev")；
2. Author 命中：提交作者必须命中规则中的任一 author (如 ["aaa"])；
3. Keyword 命中：提交内容中必须命中任一 keyword (如 ["report(bbbb)", "ccc-xxx"])。

多仓库支持：
- 无需绑定写死某个 repo，插件自动识别当前产生推送的仓库（无论是 github.com/org1/repo1 还是 org2/repo2），
  动态生成对应仓库在该分支下的指定文件直达链接。

防重机制：
- 单条提交内命中多个关键字时合并为单条通知；
- 状态持久化 (.linker_state.json) 防止跨轮询重复通知。
"""

import sys
import os
import json
import re
import subprocess
import urllib.parse
import webbrowser

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
CONFIG_EXAMPLE_FILE = os.path.join(os.path.dirname(__file__), "config.json.example")
STATE_FILE = os.path.join(os.path.dirname(__file__), ".linker_state.json")

def load_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            sys.stderr.write(f"读取 JSON 文件失败 {filepath}: {e}\n")
    return default_val

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        sys.stderr.write(f"保存状态文件失败 {filepath}: {e}\n")

def get_git_repo_path(payload):
    """尝试获取仓库本地工作区或镜像路径"""
    repo = payload.get("repo") or {}
    remote_url = repo.get("remoteUrl", "")
    if remote_url and os.path.isdir(remote_url):
        return remote_url
    project = payload.get("project") or {}
    for r in project.get("repos", []):
        p = r.get("remoteUrl", "")
        if p and os.path.isdir(p):
            return p
    return None

def run_git_cmd(repo_dir, args):
    """安全执行 git 命令获取文件内容或提交信息"""
    if not repo_dir or not os.path.isdir(repo_dir):
        return ""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8
        )
        if res.returncode == 0:
            return res.stdout
    except Exception as e:
        sys.stderr.write(f"执行 git 命令失败: {e}\n")
    return ""

def parse_remote_info(repo_info):
    """
    解析当前发生推送的仓库信息，提取 host, provider, owner/repo 等信息
    动态适配多仓库环境 (GitHub / GitLab / Gitee / Bitbucket / Gitea)
    """
    provider = (repo_info.get("provider") or "").lower()
    remote_url = (repo_info.get("remoteUrl") or "").strip()
    owner_repo = (repo_info.get("ownerRepo") or "").strip().rstrip("/")
    if owner_repo.endswith(".git"):
        owner_repo = owner_repo[:-4]

    host = ""
    parsed_path = ""

    if remote_url:
        if "://" in remote_url:
            try:
                u = urllib.parse.urlparse(remote_url)
                host = u.hostname or ""
                parsed_path = u.path.strip("/")
                if parsed_path.endswith(".git"):
                    parsed_path = parsed_path[:-4]
            except Exception:
                pass
        elif ":" in remote_url and not remote_url.startswith("/"):
            # SSH format: git@github.com:owner/repo.git
            parts = remote_url.split(":", 1)
            host_part = parts[0]
            if "@" in host_part:
                host_part = host_part.split("@", 1)[1]
            host = host_part.lower()
            parsed_path = parts[1].strip("/")
            if parsed_path.endswith(".git"):
                parsed_path = parsed_path[:-4]

    if not owner_repo and parsed_path:
        owner_repo = parsed_path

    if not host:
        if "gitlab" in provider:
            host = "gitlab.com"
        elif "gitee" in provider:
            host = "gitee.com"
        elif "bitbucket" in provider:
            host = "bitbucket.org"
        else:
            host = "github.com"

    return {
        "host": host,
        "owner_repo": owner_repo,
        "provider": provider,
        "remote_url": remote_url,
        "name": repo_info.get("name", "")
    }

def build_file_urls(remote_info, branch, commit_sha, file_path, local_repo_dir=None):
    """
    针对当前被推送的具体仓库，构建该分支下的文件直达链接
    """
    host = remote_info.get("host") or "github.com"
    owner_repo = remote_info.get("owner_repo") or ""
    provider = remote_info.get("provider") or ""

    clean_file = file_path.lstrip("/")
    clean_branch = branch.replace("refs/heads/", "") if branch else "main"
    sha = commit_sha.strip() if commit_sha else clean_branch

    branch_file_url = ""
    commit_file_url = ""
    raw_file_url = ""

    if owner_repo:
        if "gitlab" in host or provider == "gitlab":
            branch_file_url = f"https://{host}/{owner_repo}/-/blob/{clean_branch}/{clean_file}"
            commit_file_url = f"https://{host}/{owner_repo}/-/blob/{sha}/{clean_file}"
            raw_file_url = f"https://{host}/{owner_repo}/-/raw/{clean_branch}/{clean_file}"
        elif "gitee" in host or provider == "gitee":
            branch_file_url = f"https://gitee.com/{owner_repo}/blob/{clean_branch}/{clean_file}"
            commit_file_url = f"https://gitee.com/{owner_repo}/blob/{sha}/{clean_file}"
            raw_file_url = f"https://gitee.com/{owner_repo}/raw/{clean_branch}/{clean_file}"
        elif "bitbucket" in host or provider == "bitbucket":
            branch_file_url = f"https://{host}/{owner_repo}/src/{clean_branch}/{clean_file}"
            commit_file_url = f"https://{host}/{owner_repo}/src/{sha}/{clean_file}"
            raw_file_url = f"https://{host}/{owner_repo}/raw/{clean_branch}/{clean_file}"
        elif "gitea" in host or "codeberg" in host or provider == "gitea":
            branch_file_url = f"https://{host}/{owner_repo}/src/branch/{clean_branch}/{clean_file}"
            commit_file_url = f"https://{host}/{owner_repo}/src/commit/{sha}/{clean_file}"
            raw_file_url = f"https://{host}/{owner_repo}/raw/branch/{clean_branch}/{clean_file}"
        else:
            # 默认 GitHub 风格
            branch_file_url = f"https://{host}/{owner_repo}/blob/{clean_branch}/{clean_file}"
            commit_file_url = f"https://{host}/{owner_repo}/blob/{sha}/{clean_file}"
            raw_file_url = f"https://raw.githubusercontent.com/{owner_repo}/{clean_branch}/{clean_file}"

    # 本地文件链接支持（若存在本地仓库目录）
    local_file_url = ""
    vscode_url = ""
    if local_repo_dir and os.path.isdir(local_repo_dir):
        abs_file = os.path.abspath(os.path.join(local_repo_dir, clean_file))
        local_file_url = f"file://{abs_file}"
        vscode_url = f"vscode://file{abs_file}"

    return {
        "branch_file_url": branch_file_url,
        "commit_file_url": commit_file_url,
        "raw_file_url": raw_file_url,
        "local_file_url": local_file_url,
        "vscode_url": vscode_url,
        "file_path": clean_file,
        "branch": clean_branch,
        "sha": sha
    }

def clean_author_name(author):
    """规范化作者名（去除 @ 前缀、去除邮箱后缀等）"""
    if not author:
        return ""
    a = author.strip()
    if "<" in a and ">" in a:
        a = a.split("<")[0].strip()
    return a.lstrip("@").strip().lower()

def match_commit_against_rule(rule, repo_info, branch, commit):
    """
    严格判定逻辑（三者皆为 True 才执行）：
    1. Branch 命中：推送分支匹配目标分支
    2. Author 命中：提交作者属于目标作者之一
    3. Keywords 命中：提交信息包含至少一个关键字
    三者全部为 True 返回匹配上下文，任一为 False 返回 None
    """
    clean_branch = branch.replace("refs/heads/", "").strip()

    # --- 条件 1: Branch 命中判定 ---
    target_branches = rule.get("branch") or rule.get("branches")
    if not target_branches:
        return None
    if isinstance(target_branches, str):
        target_branches = [target_branches]

    branch_matched = False
    for tb in target_branches:
        tb_clean = tb.replace("refs/heads/", "").strip()
        if not tb_clean:
            continue
        if clean_branch.lower() == tb_clean.lower():
            branch_matched = True
            break
        try:
            if re.search(f"^{tb_clean}$", clean_branch, re.IGNORECASE):
                branch_matched = True
                break
        except Exception:
            pass

    if not branch_matched:
        return None

    # --- 条件 2: Author 命中判定 (命中一个即为 True) ---
    target_authors = rule.get("authors") or rule.get("author")
    if not target_authors:
        return None
    if isinstance(target_authors, str):
        target_authors = [target_authors]

    clean_target_authors = [clean_author_name(a) for a in target_authors if clean_author_name(a)]
    if not clean_target_authors:
        return None

    commit_author = clean_author_name(commit.get("author", ""))
    author_matched = False
    for ta in clean_target_authors:
        if ta == commit_author or ta in commit_author:
            author_matched = True
            break

    if not author_matched:
        return None

    # --- 条件 3: Keywords 命中判定 (命中一条即为 True) ---
    keywords = rule.get("keywords") or rule.get("keyword")
    if not keywords:
        return None
    if isinstance(keywords, str):
        keywords = [keywords]

    subject = commit.get("subject", "")
    body = commit.get("body", "")
    full_text = f"{subject}\n{body}".strip()

    matched_keywords = []
    for kw in keywords:
        if not kw:
            continue
        if kw.lower() in full_text.lower():
            if kw not in matched_keywords:
                matched_keywords.append(kw)
        else:
            try:
                m = re.search(re.escape(kw), full_text, re.IGNORECASE)
                if m and kw not in matched_keywords:
                    matched_keywords.append(kw)
            except Exception:
                pass

    # 兼容可选高级正则 patterns
    for pat in rule.get("keyword_patterns", []):
        try:
            m = re.search(pat, full_text, re.IGNORECASE)
            if m and m.group(0) not in matched_keywords:
                matched_keywords.append(m.group(0))
        except Exception:
            pass

    if not matched_keywords:
        return None

    # --- 可选条件: Repo 过滤（若用户未配置则对所有监控的仓库生效） ---
    target_repo = (rule.get("repo") or "").strip().lower()
    if target_repo and target_repo not in ("*", "all"):
        owner_repo = (repo_info.get("owner_repo") or "").lower()
        repo_name = (repo_info.get("name") or "").lower()
        remote_url = (repo_info.get("remote_url") or "").lower()
        if (target_repo not in owner_repo and
            target_repo not in repo_name and
            target_repo not in remote_url):
            return None

    # --- 获取目标文件清单 target_files ---
    target_files = rule.get("target_files") or rule.get("target_file")
    if not target_files:
        return None
    if isinstance(target_files, str):
        target_files = [target_files]

    return {
        "matched_keywords": matched_keywords,
        "target_files": list(dict.fromkeys(target_files))
    }

def get_file_snippet(repo_dir, ref, file_path, max_lines=10):
    """尝试从本地 Git 仓库获取文件的前 N 行内容预览"""
    if not repo_dir or not file_path:
        return ""
    content = run_git_cmd(repo_dir, ["show", f"{ref}:{file_path}"])
    if not content:
        content = run_git_cmd(repo_dir, ["show", f"HEAD:{file_path}"])
    if content:
        lines = content.splitlines()
        preview = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            preview += f"\n... (剩余 {len(lines) - max_lines} 行)"
        return preview
    return ""

def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            return
        payload = json.loads(raw_input)
    except Exception as e:
        sys.stderr.write(f"解析 stdin JSON 失败: {e}\n")
        return

    event = payload.get("event")
    if event != "branch_push":
        return

    repo = payload.get("repo") or {}
    branch = payload.get("branch", "")
    tip_sha = payload.get("tipSha", "")
    commits = payload.get("commits", [])

    # 如果 commits 为空但存在 tip_sha，则合成一条简易提交信息
    if not commits and tip_sha:
        commits = [{
            "sha": tip_sha,
            "shortSha": tip_sha[:7],
            "subject": "分支代码更新",
            "author": ""
        }]

    # 加载配置：优先读取用户的 config.json，若不存在则回退至 config.json.example 或默认值，绝不覆写用户配置
    default_config = {
        "rules": [
          {
            "name": "Dev 分支关键提交文件直达",
            "branch": "dev",
            "authors": ["aaa"],
            "keywords": ["report(bbbb)", "ccc-xxx"],
            "target_files": ["abc/def/xxx.md"],
            "actions": ["notify"],
            "preview_file": True,
            "preview_lines": 10,
            "auto_open_browser": False
          }
        ]
    }

    custom_cfg_path = os.environ.get("XISSUE_LINKER_CONFIG")
    if custom_cfg_path and os.path.exists(custom_cfg_path):
        config = load_json(custom_cfg_path, default_config)
    elif os.path.exists(CONFIG_FILE):
        config = load_json(CONFIG_FILE, default_config)
    elif os.path.exists(CONFIG_EXAMPLE_FILE):
        config = load_json(CONFIG_EXAMPLE_FILE, default_config)
    else:
        config = default_config

    rules = config.get("rules")
    if not rules:
        if "branch" in config or "keywords" in config:
            rules = [config]
        else:
            rules = default_config["rules"]

    remote_info = parse_remote_info(repo)
    local_repo_dir = get_git_repo_path(payload)
    clean_branch = branch.replace("refs/heads/", "").strip()

    # 加载已处理的提交历史，防止多次轮询导致重复通知
    state = load_json(STATE_FILE, {"handled_commits": []})
    handled_history = set(state.get("handled_commits", []))

    actions = []
    processed_in_this_run = set()
    newly_handled_keys = []

    # 核心原则：单条提交记录在所有规则中最多只命中并推送一次！
    for commit in commits:
        commit_sha = commit.get("sha") or tip_sha
        short_sha = commit.get("shortSha") or (commit_sha[:7] if commit_sha else "")
        author = commit.get("author") or "未知作者"
        subject = commit.get("subject") or "无提交标题"

        # 构建提交的全局唯一标识（关联具体仓库、分支与 commit SHA）
        repo_identifier = remote_info.get("owner_repo") or remote_info.get("name") or "unknown_repo"
        commit_key = f"{repo_identifier}:{clean_branch}:{commit_sha}"

        # 检查是否已在历史记录或本次运行中处理过
        if commit_key in handled_history or commit_sha in handled_history:
            continue
        if commit_key in processed_in_this_run or commit_sha in processed_in_this_run:
            continue

        # 逐个规则匹配：branch && author && keyword 三者全为 True 时触发
        for rule in rules:
            match_res = match_commit_against_rule(rule, remote_info, branch, commit)
            if not match_res:
                continue

            # 标记该提交已经被处理，防止再次命中
            processed_in_this_run.add(commit_key)
            processed_in_this_run.add(commit_sha)
            newly_handled_keys.append(commit_key)
            newly_handled_keys.append(commit_sha)

            rule_actions = rule.get("actions", ["notify"])
            preview_enabled = rule.get("preview_file", True)
            preview_lines = rule.get("preview_lines", 10)
            auto_open = rule.get("auto_open_browser", False)

            matched_keywords = match_res["matched_keywords"]
            target_files = match_res["target_files"]

            # 组装通知 Markdown 消息（全面兼容 Telegram 与各大移动端 Markdown 渲染引擎）
            display_repo = remote_info.get("owner_repo") or remote_info.get("name") or "Repo"
            msg_lines = [
                f"🎯 *【{display_repo}:{clean_branch}】命中监控规则：文件直达*",
                f"• *仓库*: `{display_repo}`",
                f"• *监控分支*: `{clean_branch}`",
                f"• *提交作者*: `@{author}`",
                f"• *提交说明*: {subject} (`{short_sha}`)",
                f"• *命中关键字*: {', '.join([f'`{k}`' for k in matched_keywords])}",
                "",
                "🔗 *文件直达链接:*"
            ]

            first_browser_url = None

            for tf in target_files:
                urls = build_file_urls(remote_info, branch, commit_sha, tf, local_repo_dir)
                branch_url = urls["branch_file_url"]
                commit_url = urls["commit_file_url"]
                raw_url = urls["raw_file_url"]
                vscode_url = urls["vscode_url"]

                if not first_browser_url and branch_url:
                    first_browser_url = branch_url

                if len(target_files) > 1:
                    msg_lines.append(f"\n📄 *文件: {tf}*")

                if branch_url:
                    msg_lines.append(f"• 🌐 [打开分支指定文件: {tf}]({branch_url})")
                if commit_url:
                    msg_lines.append(f"• 🔍 [查看本次提交快照版本]({commit_url})")
                if raw_url:
                    msg_lines.append(f"• 📄 [查看原始文件 (Raw)]({raw_url})")
                if vscode_url:
                    msg_lines.append(f"• 💻 [在 VS Code 本地打开]({vscode_url})")

                # 提取文件内容预览（若本地存在镜像或工作区）
                if preview_enabled and local_repo_dir:
                    file_snippet = get_file_snippet(local_repo_dir, commit_sha, tf, preview_lines)
                    if file_snippet:
                        msg_lines.extend([
                            "",
                            f"📄 *{tf} 内容预览 (前 {preview_lines} 行):*",
                            "```",
                            file_snippet,
                            "```"
                        ])

            full_message = "\n".join(msg_lines).strip()

            # 1. 派发 notify 动作（单条提交仅派发一次）
            if "notify" in rule_actions:
                actions.append({
                    "type": "notify",
                    "message": full_message
                })

            # 2. 派发 create_issue 动作（若配置）
            if "create_issue" in rule_actions:
                actions.append({
                    "type": "create_issue",
                    "prompt": f"[自动跟进] [{display_repo}:{clean_branch}] 关键文件更新: {', '.join(target_files)} (由 @{author} 提交: {subject})"
                })

            # 3. 宿主机环境自动打开浏览器（若配置开启）
            if auto_open and first_browser_url:
                try:
                    webbrowser.open(first_browser_url)
                except Exception as e:
                    sys.stderr.write(f"调用浏览器打开链接失败: {e}\n")

            # 已经有规则命中此条提交，跳出规则匹配，不再重复处理
            break

    # 更新持久化状态文件，保持最近 500 个提交记录
    if newly_handled_keys and os.environ.get("XISSUE_NO_SAVE_STATE") != "1":
        merged = state.get("handled_commits", []) + newly_handled_keys
        seen = set()
        deduped = []
        for k in reversed(merged):
            if k not in seen:
                seen.add(k)
                deduped.append(k)
        state["handled_commits"] = list(reversed(deduped))[-500:]
        save_json(STATE_FILE, state)

    # 输出指令动作供 xIssue 执行
    if actions:
        print(json.dumps({"actions": actions}, ensure_ascii=False))

if __name__ == "__main__":
    main()
