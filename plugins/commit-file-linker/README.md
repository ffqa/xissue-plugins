# 插件：commit-file-linker（指定分支/作者/关键字提交文件直达）

这是一个专为 **xIssue** 开发的高级提交监控与文件导航插件。

## 🎯 核心解决场景

在多分支并行开发或自动化构建场景中，开发者经常有类似诉求：
> “在监控到指定分支收到指定成员的推送时，如果提交标题或说明中带有某个业务关键字（如报告生成、模块变更等），希望能第一时间在通知里获得一个直接打开该分支下指定文件的超链接，甚至直接预览该文件最新内容或在本地编辑器中打开。”

### 典型示例：
- **监控仓库**: `github.com/xxx/yyy` (同时支持 GitLab、Gitee、Bitbucket 等)
- **监控分支**: `dev`
- **监控提交人**: `aaa`
- **提交内容关键字**: `report(bbbb)` 或 `ccc-xxx` 等
- **直达文件**: `abc/def/xxx.md`
- **生成效果**: 自动生成 `https://github.com/xxx/yyy/blob/dev/abc/def/xxx.md` 直达链接，并推送通知到桌面弹窗、飞书/企微/钉钉/Telegram。

---

## 🌟 核心特性

1. **三维精准命中匹配**：
   - **分支过滤**：支持指定分支精确匹配（如 `dev`）或正则匹配（如 `release/.*`）；
   - **提交人过滤**：支持关注特定成员列表（如 `["aaa", "@bbb"]`），不区分大小写，自动处理 `@` 与邮箱；
   - **内容模式匹配**：支持子串关键字（如 `report(bbbb)`、`ccc-xxx`）或正则表达式（带命名捕获组）；
2. **多平台文件 URL 自动组装**：
   - 自动识别仓库托管商（GitHub、GitLab、Gitee、Bitbucket、自建 Gitea 等）；
   - 生成 **分支最新文件直达链接** (`.../blob/dev/abc/def/xxx.md`)；
   - 生成 **本次提交版本快照链接** (`.../blob/<commit_sha>/abc/def/xxx.md`)；
   - 生成 **原始数据 (Raw) 链接**；
   - 若本地存在工作区，额外提供 **VS Code 协议直达链接** (`vscode://file/...`)；
3. **严格防重与消息聚合（防止重复通知）**：
   - **单提交多关键字聚合**：同一条提交记录如果同时包含多个关键字（例如既有 `report(bbbb)` 又有 `ccc-xxx`），自动汇总所有匹配项与直达链接，**严格只推送 1 条通知**；
   - **多目标文件汇总**：单条提交若涉及多个目标文件，整合到单条通知中分段呈现，避免按文件循环推送多次通知；
   - **多规则短路防重**：单条提交一旦被优先级更高的规则处理，自动跳出，避免被多条规则重复命中；
   - **跨轮询持久化状态**：通过 `.linker_state.json` 自动记录已推送过的 Commit SHA，轮询扫描或重试事件中绝不重复触发。
4. **轻量无外部依赖**：
   - 纯 Python 3 标准库实现，无需 `pip install` 任何三方包；
   - 15 秒超时保护与沙箱隔离执行。

---

## ⚙️ 配置文件说明 (`config.json`)

在插件目录下放置 `config.json`（已内置默认配置）：

```json
{
  "rules": [
    {
      "name": "Dev 分支关键提交文件直达",
      "branch": "dev",
      "authors": ["aaa"],
      "keywords": [
        "report(bbbb)",
        "ccc-xxx"
      ],
      "target_files": [
        "abc/def/xxx.md"
      ],
      "actions": [
        "notify"
      ],
      "preview_file": true,
      "preview_lines": 10,
      "auto_open_browser": false
    }
  ]
}
```

### 🎯 核心判定规则（严格逻辑与）

必须同时满足以下**三个条件**（全为 `True` 时触发，任一为 `False` 即忽略）：
1. **`branch` 命中**：推送分支必须为规则指定的目标分支（如 `dev`）；
2. **`authors` 命中一个**：提交人命中列表中的任意作者（如 `aaa`）；
3. **`keywords` 命中一条**：提交信息命中列表中的任意关键字（如 `report(bbbb)` 或 `ccc-xxx`）。

### 🌐 多仓库无缝适配
- **无需写死具体 repo**：规则中无需配置 `repo` 字段，插件自动监听所有受控仓库；
- 当监控的 `repo-A` 收到符合条件的推送时，自动组装生成 `repo-A` 对应分支下的文件直达链接；当 `repo-B` 收到推送时，同样自动组装 `repo-B` 的文件直达链接。

### 配置项详细说明：

| 配置字段 | 类型 | 是否必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `branch` | string / array | **必填** | 目标分支（支持精确或正则），满足其一为 True | `"dev"` 或 `["dev", "main"]` |
| `authors` | string / array | **必填** | 目标提交人列表，满足其一为 True（自动剥离 `@` 与邮箱） | `["aaa", "ci-bot"]` |
| `keywords` | string / array | **必填** | 提交信息包含的关键字，满足其一为 True | `["report(bbbb)", "ccc-xxx"]` |
| `target_files` | string / array | **必填** | 需要生成直达链接的目标文件路径 | `["abc/def/xxx.md"]` |
| `repo` | string | *选填* | 仅在需要限定个别特殊仓库时配置；不配置或留空则**自动对所有受控仓库生效** | `"xxx/yyy"` |
| `actions` | array | *选填* | 命中后执行动作，默认 `["notify"]`，可选 `"create_issue"` | `["notify"]` |
| `preview_file` | boolean| *选填* | 本地存在仓库时是否在通知中提取该文件内容预览，默认 `true` | `true` |
| `preview_lines`| integer| *选填* | 文件内容预览的最大行数，默认 `10` | `10` |

---

## 🚀 安装与加载

将本目录拷贝或软链接至 xIssue 全局插件目录：

```bash
mkdir -p ~/.xissue/plugins
cp -r plugins/commit-file-linker ~/.xissue/plugins/
```

xIssue 会自动扫描并在 `GET /api/plugins` 及前端页面中呈现此插件。

---

## 🔍 本地调试与验证

无需等待后台 Git 推送，可直接在终端中管道喂入 Mock JSON 进行调试：

```bash
python3 plugins/commit-file-linker/run.py << 'EOF'
{
  "event": "branch_push",
  "project": { "id": 1, "name": "my-project" },
  "repo": {
    "ownerRepo": "xxx/yyy",
    "name": "yyy",
    "remoteUrl": "https://github.com/xxx/yyy.git",
    "provider": "github"
  },
  "branch": "dev",
  "tipSha": "34639b4f9812e1234567890abcdef12345678",
  "commits": [
    {
      "sha": "34639b4f9812e1234567890abcdef12345678",
      "shortSha": "34639b4",
      "subject": "report(bbbb): weekly QA analysis",
      "author": "aaa"
    }
  ]
}
EOF
```

控制台会即时输出带有 Markdown 超链接的 `notify` Action：
```json
{
  "actions": [
    {
      "type": "notify",
      "message": "🎯 **[xxx/yyy:dev] 命中监控规则：文件直达**\n- **监控分支**: `dev`\n- **提交作者**: `@aaa`\n- **提交说明**: report(bbbb): weekly QA analysis (`34639b4`)\n- **命中关键字**: `report(bbbb)`\n\n---\n### 🔗 文件直达链接\n- 🌐 **[打开分支指定文件: `abc/def/xxx.md`](https://github.com/xxx/yyy/blob/dev/abc/def/xxx.md)**\n- 🔍 [查看本次提交快照版本](https://github.com/xxx/yyy/blob/34639b4f9812e1234567890abcdef12345678/abc/def/xxx.md)\n- 📄 [查看原始文件 (Raw)](https://raw.githubusercontent.com/xxx/yyy/dev/abc/def/xxx.md)"
    }
  ]
}
```

也可以直接运行自动化测试套件：
```bash
python3 plugins/commit-file-linker/test_plugin.py
```
