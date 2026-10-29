# xIssue Plugins

First-party and community plugins for [xIssue](https://github.com/ffqa/xissue).

Install from the catalog:

```bash
xissue plugin install custom-notifier
xissue plugin install follow-commit-watcher
xissue plugin install slack-notifier
xissue plugin install run-audit
xissue plugin install commit-file-linker
xissue plugin install ui-demo
xissue plugin list
```

Install any GitHub plugin directly:

```bash
xissue plugin install your-user/your-plugin
xissue plugin install your-user/monorepo --path plugins/my-plugin --force
```

The installer clones the repository, validates `plugin.yaml` against API v1,
and copies only the selected plugin directory into `~/.xissue/plugins/<name>`.
Existing installs are preserved unless `--force` is passed.

## Catalog

| Plugin | Events | Purpose |
|---|---|---|
| `custom-notifier` | `notification_dispatch` | Feishu, WeCom, DingTalk, Bark, macOS desktop |
| `follow-commit-watcher` | `branch_push`, `pr_merged` | Post-merge and selected-author commit tracking |
| `slack-notifier` | `notification_dispatch` | Slack incoming webhook |
| `run-audit` | `run_started`, `run_finished` | JSONL audit log and failure notification |
| `commit-file-linker` | `branch_push` | Link matching branch/author/keyword commits to a target file (web + local editor) |
| `ui-demo` | `notification_dispatch` | Standalone plugin page plus `project.page` / `issue.actions` slots |

`index.json` is the machine-readable catalog consumed by xIssue. Entries may
point at another repository with a `repo` and `path`.

## Contract

Plugins use manifest API v1. Build one from
[xissue-plugin-template](https://github.com/ffqa/xissue-plugin-template).

- stdin: one JSON event payload.
- stdout: `{"actions": [...]}` or empty.
- timeout: 15 seconds per invocation.
- UI slots: `project.header`, `project.page`, `project.toolbar`, `issue.actions`, `issue.page`, `issue.toolbar`; toolbar slots can request a host modal via `xissue:open-modal`.
- AI: `GET /api/plugins/ai` returns the default agent; `POST /api/plugins/ai` runs a text-only prompt. Sandboxed UIs use the `xissue:ai` / `xissue:ai-result` bridge.
- lifecycle events use an explicit event/action allowlist (labels, follow-up issues,
  PR review runs) with recursion guards; see the plugin guide for the matrix.
- plugins run as your user; `permissions` are declarations, not a sandbox.

Full event and action documentation:
[xIssue plugin guide](https://github.com/ffqa/xissue/blob/main/docs/PLUGINS_AND_HOOKS.md).

## Development

```bash
python3 scripts/validate_manifest.py plugins/custom-notifier
printf '%s' '{"event":"notification_dispatch","notification":{"title":"hi","body":"test"}}' \
  | plugins/custom-notifier/run.py
```

CI validates every manifest and runs smoke payloads for each plugin.

## Security

Plugins execute local code with your account's permissions. Review a plugin
before installing it. Never put long-lived secrets in a repository; use
`config.json` in the installed directory (gitignored) or environment variables.

## Adding a plugin

1. Create `plugins/<name>/` with `plugin.yaml`, `run.py` (or `run.js`/`run.sh`),
   `README.md`, and `config.example.json`.
2. Add tests to `.github/workflows/validate.yml`.
3. Add an entry to `index.json`.
4. Bump versions in both the manifest and the index.

## License

MIT
