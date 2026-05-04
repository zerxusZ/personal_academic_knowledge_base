# Claude Code 工作规程

本文件由 Claude Code 在每次会话开始时自动读取。
它定义了对本项目进行任何修改时**必须遵守**的工作流程。

---

## 强制工作流程

### 改动前（无论改动大小）

1. **读取** `ARCHITECTURE.md` —— 确认当前架构状态
2. **读取** `DESIGN_INTENT.md` —— 确认改动是否符合设计意图
3. 如果改动与 `DESIGN_INTENT.md` 中"不做什么"一节有冲突，**必须先告知用户并说明原因**，再决定是否继续

### 改动后

1. **更新** `ARCHITECTURE.md` —— 同步反映新的结构、端点、数据模型
2. **更新** `DESIGN_INTENT.md` —— 在"变更历史"表格中追加一行，如果本次改动涉及原则性决策，在对应章节补充说明
3. 两个文件的更新**必须在同一次对话中完成**，不能留到"下次"

---

## 文件优先级

```
CLAUDE.md           ← 工作规程（本文件）
ARCHITECTURE.md     ← 架构事实（做了什么）
DESIGN_INTENT.md    ← 设计意图（为什么这样做）
源代码              ← 实现
```

当文档与代码不一致时，**以文档为准**并修复代码，而不是更新文档去迁就错误的代码。

---

## 项目快速上下文

| 项目 | 描述 |
|------|------|
| 语言 | Python 3.11+，原生 HTML/CSS/JS |
| 框架 | FastAPI + uvicorn |
| 核心功能 | 来源摄取 → LLM 语义标签 → Jaccard 聚类 → 知识地图 |
| 目标用户 | **非 CS 背景**研究者 |
| 数据存储 | JSON 文件（`data/knowledge_base/sources.json`） |
| LLM | 支持 Anthropic / OpenAI / Gemini，通过 `.env` 切换 |
| 运行方式 | `python main.py`，访问 `http://localhost:8000` |

---

## 代码风格约定

- **不写注释**，除非逻辑非显而易见（隐藏约束、绕过 bug、反直觉的不变量）
- **不写防御性代码**应对不可能发生的场景
- **不做超出需求的抽象**：三段相似代码才考虑提取，不提前封装
- LLM prompt 放在服务层（`services/`），不放在路由层（`api/routes/`）
- 所有新服务必须通过 `logging.getLogger("name")` 接入日志系统
- 所有新路由必须在 `ARCHITECTURE.md` 的"API 端点一览"表格中登记

---

## 新增 LLM Provider 检查清单

- [ ] 继承 `BaseLLM`，实现 `chat()` + `available()`
- [ ] 在 `services/llm/__init__.py` 的 `candidates` 字典注册
- [ ] 在 `config.py` 添加 API key 字段
- [ ] 在 `ARCHITECTURE.md` "当前支持的 provider" 列表更新
- [ ] 在 `.env.example` 添加对应 key 示例

## 新增 API 路由检查清单

- [ ] 在 `main.py` include_router
- [ ] 在 `ARCHITECTURE.md` "API 端点一览"表格登记
- [ ] 确认与 `DESIGN_INTENT.md` "功能边界：不做什么"不冲突

---

## 敏感文件保护

下列文件**绝对不能**出现在 git 提交中：

```
.env
data/profile.json
data/knowledge_base/*.json
logs/
```

如果用户要求提交这些文件，**拒绝并解释原因**。
