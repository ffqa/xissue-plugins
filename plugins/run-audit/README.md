# run-audit

Append `run_started` and `run_finished` events to `audit.jsonl` next to the
plugin. On failure it returns a `notify` action (the only mutating action
supported for lifecycle events).

```bash
cp config.example.json config.json
xissue plugin install run-audit
```

Set `log_file` to an absolute path to keep audits outside the plugin directory.
