# custom-notifier

Forward every xIssue in-app notification to one or more external channels.

Supported: Feishu interactive cards, WeCom markdown, DingTalk markdown with
optional HMAC signing, Bark (iOS), and macOS desktop notifications.

## Configure

```bash
cp config.example.json config.json
# edit config.json
```

All channels are optional. Leave a webhook empty to disable it.

## Install

```bash
xissue plugin install custom-notifier
```

`config.json` and runtime files are gitignored. Permissions declared:
`network`, `process`.

## Test

```bash
printf '%s' '{"event":"notification_dispatch","notification":{"title":"test","body":"hello","link":"/projects/1"}}' | ./run.py
```
