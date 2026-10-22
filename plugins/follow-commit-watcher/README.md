# follow-commit-watcher

Watches a branch after a PR merge and for selected commit authors.

- `pr_merged` records the PR and resets the post-merge counter for that PR's base branch.
- `branch_push` inspects up to `max_post_merge_check` commits after that merge.
- Selected authors are tracked on every branch push.
- Changed files are listed; watched files get a 10-line preview via `git show`.
- Keyword matches emit `create_issue` actions.

## Configure

```bash
cp config.example.json config.json
```

`target_authors` are exact git author names (`alice`, not `alice-bot`) after
trimming a leading `@` and lowercasing. `mirrors_dir` is used when the event's
repository has no local working tree; xIssue mirrors are bare repositories and
work with `git show`.

State is kept in `state.json` next to the plugin.

## Install

```bash
xissue plugin install follow-commit-watcher
```
