#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit-file-linker 插件自动化测试套件
验证多仓库支持、严格的三条件与逻辑 (branch && author && keyword) 以及防重聚合机制
"""

import unittest
import json
import subprocess
import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_SCRIPT = os.path.join(PLUGIN_DIR, "run.py")
STATE_FILE = os.path.join(PLUGIN_DIR, ".linker_state.json")

class TestCommitFileLinker(unittest.TestCase):

    def setUp(self):
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)

    def tearDown(self):
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)

    def run_plugin(self, payload):
        """调用 run.py 并返回解析后的 stdout JSON（使用 config.json.example 进行隔离测试）"""
        env = dict(os.environ)
        env["XISSUE_LINKER_CONFIG"] = os.path.join(PLUGIN_DIR, "config.json.example")
        proc = subprocess.run(
            [sys.executable, RUN_SCRIPT],
            input=json.dumps(payload, ensure_ascii=False),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PLUGIN_DIR,
            env=env
        )
        self.assertEqual(proc.returncode, 0, f"Plugin failed: {proc.stderr}")
        stdout = proc.stdout.strip()
        if not stdout:
            return {"actions": []}
        return json.loads(stdout)

    def test_multi_repo_support(self):
        """测试同时监控多个仓库：未限定 repo 时，所有受控仓库自动使用各自的 ownerRepo 生成链接"""
        # 1. 监控仓库 A: foo/bar
        payload_repo_a = {
            "event": "branch_push",
            "repo": {
                "ownerRepo": "foo/bar",
                "remoteUrl": "https://github.com/foo/bar.git",
                "provider": "github"
            },
            "branch": "dev",
            "commits": [
                {
                    "sha": "aaaa111122223333444455556666777788889999",
                    "shortSha": "aaaa111",
                    "subject": "report(bbbb): generated report",
                    "author": "aaa"
                }
            ]
        }
        res_a = self.run_plugin(payload_repo_a)
        actions_a = res_a.get("actions", [])
        self.assertEqual(len(actions_a), 1)
        self.assertIn("https://github.com/foo/bar/blob/dev/abc/def/xxx.md", actions_a[0]["message"])
        self.assertIn("foo/bar", actions_a[0]["message"])

        # 2. 监控仓库 B: alpha/beta
        payload_repo_b = {
            "event": "branch_push",
            "repo": {
                "ownerRepo": "alpha/beta",
                "remoteUrl": "https://github.com/alpha/beta.git",
                "provider": "github"
            },
            "branch": "dev",
            "commits": [
                {
                    "sha": "bbbb111122223333444455556666777788889999",
                    "shortSha": "bbbb111",
                    "subject": "feat: finish ccc-xxx module",
                    "author": "aaa"
                }
            ]
        }
        res_b = self.run_plugin(payload_repo_b)
        actions_b = res_b.get("actions", [])
        self.assertEqual(len(actions_b), 1)
        self.assertIn("https://github.com/alpha/beta/blob/dev/abc/def/xxx.md", actions_b[0]["message"])
        self.assertIn("alpha/beta", actions_b[0]["message"])

    def test_strict_three_conditions_true(self):
        """三个条件皆为 True: branch=dev, author=aaa, keyword=report(bbbb) -> 执行操作"""
        payload = {
            "event": "branch_push",
            "repo": {
                "ownerRepo": "xxx/yyy",
                "remoteUrl": "https://github.com/xxx/yyy.git"
            },
            "branch": "dev",
            "commits": [
                {
                    "sha": "1111222233334444555566667777888899990000",
                    "shortSha": "1111222",
                    "subject": "update: report(bbbb)",
                    "author": "aaa"
                }
            ]
        }
        res = self.run_plugin(payload)
        self.assertEqual(len(res.get("actions", [])), 1)
        msg = res["actions"][0]["message"]
        self.assertIn("https://github.com/xxx/yyy/blob/dev/abc/def/xxx.md", msg)

    def test_branch_mismatch_fails_condition(self):
        """branch 不匹配 (main != dev) -> 结果为 False，不执行操作"""
        payload = {
            "event": "branch_push",
            "repo": { "ownerRepo": "xxx/yyy" },
            "branch": "main",
            "commits": [
                {
                    "sha": "2222222222222222222222222222222222222222",
                    "subject": "report(bbbb)",
                    "author": "aaa"
                }
            ]
        }
        res = self.run_plugin(payload)
        self.assertEqual(len(res.get("actions", [])), 0)

    def test_author_mismatch_fails_condition(self):
        """author 不匹配 (bob != aaa) -> 结果为 False，不执行操作"""
        payload = {
            "event": "branch_push",
            "repo": { "ownerRepo": "xxx/yyy" },
            "branch": "dev",
            "commits": [
                {
                    "sha": "3333333333333333333333333333333333333333",
                    "subject": "report(bbbb)",
                    "author": "bob"
                }
            ]
        }
        res = self.run_plugin(payload)
        self.assertEqual(len(res.get("actions", [])), 0)

    def test_keyword_mismatch_fails_condition(self):
        """keyword 不匹配 (未命中 report(bbbb) 或 ccc-xxx) -> 结果为 False，不执行操作"""
        payload = {
            "event": "branch_push",
            "repo": { "ownerRepo": "xxx/yyy" },
            "branch": "dev",
            "commits": [
                {
                    "sha": "4444444444444444444444444444444444444444",
                    "subject": "fix: update docs and formatting",
                    "author": "aaa"
                }
            ]
        }
        res = self.run_plugin(payload)
        self.assertEqual(len(res.get("actions", [])), 0)

    def test_single_commit_multiple_keywords_single_notification(self):
        """同条记录同时命中多个关键字时，严格只推 1 条通知"""
        payload = {
            "event": "branch_push",
            "repo": { "ownerRepo": "xxx/yyy" },
            "branch": "dev",
            "commits": [
                {
                    "sha": "5555555555555555555555555555555555555555",
                    "shortSha": "5555555",
                    "subject": "report(bbbb): also implements ccc-xxx",
                    "author": "aaa"
                }
            ]
        }
        res = self.run_plugin(payload)
        self.assertEqual(len(res.get("actions", [])), 1)

    def test_persistent_deduplication(self):
        """已处理过的提交，第二次执行时绝对不重复命中与推送"""
        payload = {
            "event": "branch_push",
            "repo": { "ownerRepo": "xxx/yyy" },
            "branch": "dev",
            "commits": [
                {
                    "sha": "6666666666666666666666666666666666666666",
                    "subject": "ccc-xxx release",
                    "author": "aaa"
                }
            ]
        }
        res1 = self.run_plugin(payload)
        self.assertEqual(len(res1.get("actions", [])), 1)

        res2 = self.run_plugin(payload)
        self.assertEqual(len(res2.get("actions", [])), 0)

if __name__ == "__main__":
    unittest.main()
