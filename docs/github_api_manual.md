# GitHub API 管理操作手册

本手册介绍如何通过 GitHub REST API 对 **Academic Knowledge Base** 项目进行版本管理、自动化发布和 CI/CD 集成操作。

---

## 目录

1. [认证方式](#1-认证方式)
2. [仓库管理](#2-仓库管理)
3. [分支与提交](#3-分支与提交)
4. [Pull Request 流程](#4-pull-request-流程)
5. [Release 发布](#5-release-发布)
6. [GitHub Actions CI/CD](#6-github-actions-cicd)
7. [知识库文件同步](#7-知识库文件同步)
8. [常用 curl 速查](#8-常用-curl-速查)

---

## 1. 认证方式

### 推荐：Personal Access Token (PAT)

```bash
# 在 GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
# 勾选权限：Contents (read/write), Pull requests (read/write), Actions (read/write)

export GITHUB_TOKEN="github_pat_xxxxxxxx"
export GITHUB_USER="your-username"
export REPO="academic-kb"
```

所有请求在 Header 中携带：

```
Authorization: Bearer $GITHUB_TOKEN
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

---

## 2. 仓库管理

### 2.1 创建仓库

```bash
curl -X POST https://api.github.com/user/repos \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -d '{
    "name": "academic-kb",
    "description": "Academic Knowledge Base with LLM enrichment",
    "private": false,
    "auto_init": true
  }'
```

### 2.2 获取仓库信息

```bash
curl https://api.github.com/repos/$GITHUB_USER/$REPO \
  -H "Authorization: Bearer $GITHUB_TOKEN"
```

### 2.3 更新仓库描述 / Topics

```bash
curl -X PATCH https://api.github.com/repos/$GITHUB_USER/$REPO \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{
    "description": "Academic search + LLM knowledge base",
    "topics": ["nlp", "knowledge-base", "fastapi", "llm"]
  }'
```

### 2.4 删除仓库（危险操作，不可逆）

```bash
curl -X DELETE https://api.github.com/repos/$GITHUB_USER/$REPO \
  -H "Authorization: Bearer $GITHUB_TOKEN"
```

---

## 3. 分支与提交

### 3.1 列出所有分支

```bash
curl https://api.github.com/repos/$GITHUB_USER/$REPO/branches \
  -H "Authorization: Bearer $GITHUB_TOKEN"
```

### 3.2 创建新分支

```bash
# 先获取 main 分支的 SHA
SHA=$(curl -s https://api.github.com/repos/$GITHUB_USER/$REPO/git/ref/heads/main \
  -H "Authorization: Bearer $GITHUB_TOKEN" | jq -r '.object.sha')

# 基于 main 创建 feature/my-feature
curl -X POST https://api.github.com/repos/$GITHUB_USER/$REPO/git/refs \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d "{\"ref\": \"refs/heads/feature/my-feature\", \"sha\": \"$SHA\"}"
```

### 3.3 推送/更新文件（通过 API 提交单文件）

```bash
# 将 data/knowledge_base/kb.json 推送到仓库
CONTENT=$(base64 -w0 data/knowledge_base/kb.json)

# 如果文件已存在需要获取当前 SHA
FILE_SHA=$(curl -s https://api.github.com/repos/$GITHUB_USER/$REPO/contents/data/kb.json \
  -H "Authorization: Bearer $GITHUB_TOKEN" | jq -r '.sha // empty')

curl -X PUT https://api.github.com/repos/$GITHUB_USER/$REPO/contents/data/kb.json \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d "{
    \"message\": \"chore: update knowledge base\",
    \"content\": \"$CONTENT\",
    \"sha\": \"$FILE_SHA\",
    \"branch\": \"main\"
  }"
```

### 3.4 删除文件

```bash
FILE_SHA=$(curl -s https://api.github.com/repos/$GITHUB_USER/$REPO/contents/data/kb.json \
  -H "Authorization: Bearer $GITHUB_TOKEN" | jq -r '.sha')

curl -X DELETE https://api.github.com/repos/$GITHUB_USER/$REPO/contents/data/kb.json \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d "{\"message\": \"remove old kb\", \"sha\": \"$FILE_SHA\"}"
```

---

## 4. Pull Request 流程

### 4.1 创建 PR

```bash
curl -X POST https://api.github.com/repos/$GITHUB_USER/$REPO/pulls \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{
    "title": "feat: add Semantic Scholar integration",
    "body": "## Summary\n- Added `semantic_scholar.py` service\n- Wired to `/search/semantic_scholar` endpoint",
    "head": "feature/semantic-scholar",
    "base": "main"
  }'
```

### 4.2 列出所有 PR

```bash
curl "https://api.github.com/repos/$GITHUB_USER/$REPO/pulls?state=open" \
  -H "Authorization: Bearer $GITHUB_TOKEN"
```

### 4.3 合并 PR

```bash
PR_NUMBER=3
curl -X PUT https://api.github.com/repos/$GITHUB_USER/$REPO/pulls/$PR_NUMBER/merge \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{"merge_method": "squash", "commit_title": "feat: semantic scholar integration (#3)"}'
```

### 4.4 关闭 PR（不合并）

```bash
curl -X PATCH https://api.github.com/repos/$GITHUB_USER/$REPO/pulls/$PR_NUMBER \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{"state": "closed"}'
```

---

## 5. Release 发布

### 5.1 创建 Release（含知识库快照）

```bash
curl -X POST https://api.github.com/repos/$GITHUB_USER/$REPO/releases \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{
    "tag_name": "v1.0.0",
    "target_commitish": "main",
    "name": "v1.0.0 — Initial Release",
    "body": "## Changes\n- Multi-LLM support (OpenAI / Anthropic / Gemini)\n- arXiv + Semantic Scholar search\n- Standard KB export/import format",
    "draft": false,
    "prerelease": false
  }'
```

### 5.2 上传 Release Asset（附加 kb.json）

```bash
RELEASE_ID=<id from step above>
curl -X POST \
  "https://uploads.github.com/repos/$GITHUB_USER/$REPO/releases/$RELEASE_ID/assets?name=kb.json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @data/knowledge_base/kb.json
```

### 5.3 列出所有 Release

```bash
curl https://api.github.com/repos/$GITHUB_USER/$REPO/releases \
  -H "Authorization: Bearer $GITHUB_TOKEN"
```

---

## 6. GitHub Actions CI/CD

将以下文件放到 `.github/workflows/ci.yml` 实现自动测试 + 部署：

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt pytest httpx

      - name: Run tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: pytest tests/ -v

  docker-build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t academic-kb:latest .
```

### 触发 Workflow（手动）

```bash
curl -X POST \
  https://api.github.com/repos/$GITHUB_USER/$REPO/actions/workflows/ci.yml/dispatches \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{"ref": "main"}'
```

### 查看 Workflow 运行状态

```bash
curl https://api.github.com/repos/$GITHUB_USER/$REPO/actions/runs \
  -H "Authorization: Bearer $GITHUB_TOKEN" | jq '.workflow_runs[0] | {status, conclusion, html_url}'
```

---

## 7. 知识库文件同步

本项目的 `data/knowledge_base/kb.json` 可以通过 GitHub API 实现自动同步，供其他项目拉取：

### 7.1 其他项目拉取最新 KB

```python
import httpx, base64, json

async def fetch_kb_from_github(owner: str, repo: str, token: str) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/data/kb.json"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        content = base64.b64decode(resp.json()["content"]).decode()
        return json.loads(content)
```

### 7.2 推送更新后的 KB

```python
async def push_kb_to_github(kb: dict, owner: str, repo: str, token: str):
    import base64, json, httpx
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/data/kb.json"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    content_b64 = base64.b64encode(json.dumps(kb, ensure_ascii=False, indent=2).encode()).decode()

    async with httpx.AsyncClient() as client:
        # Get current SHA if file exists
        get_resp = await client.get(url, headers=headers)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
        body = {"message": "chore: sync knowledge base", "content": content_b64}
        if sha:
            body["sha"] = sha
        await client.put(url, headers=headers, json=body)
```

---

## 8. 常用 curl 速查

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取仓库信息 | GET | `/repos/{owner}/{repo}` |
| 列出分支 | GET | `/repos/{owner}/{repo}/branches` |
| 创建分支 | POST | `/repos/{owner}/{repo}/git/refs` |
| 获取文件内容 | GET | `/repos/{owner}/{repo}/contents/{path}` |
| 创建/更新文件 | PUT | `/repos/{owner}/{repo}/contents/{path}` |
| 删除文件 | DELETE | `/repos/{owner}/{repo}/contents/{path}` |
| 创建 PR | POST | `/repos/{owner}/{repo}/pulls` |
| 合并 PR | PUT | `/repos/{owner}/{repo}/pulls/{pr}/merge` |
| 创建 Release | POST | `/repos/{owner}/{repo}/releases` |
| 上传 Release Asset | POST | `https://uploads.github.com/repos/{owner}/{repo}/releases/{id}/assets` |
| 触发 Workflow | POST | `/repos/{owner}/{repo}/actions/workflows/{id}/dispatches` |
| 查看 Workflow 运行 | GET | `/repos/{owner}/{repo}/actions/runs` |

---

> **提示：** 所有需要 `jq` 的命令在 Windows 上可用 PowerShell 的 `ConvertFrom-Json` 替代，或者直接安装 [jq for Windows](https://jqlang.github.io/jq/download/)。
