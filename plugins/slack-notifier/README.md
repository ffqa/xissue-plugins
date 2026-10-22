# slack-notifier

Sends xIssue notifications to Slack.

```bash
cp config.example.json config.json
# set webhook_url, or export SLACK_WEBHOOK_URL
xissue plugin install slack-notifier
```

`base_url` converts relative xIssue links (`/issues/12`) into clickable links.
