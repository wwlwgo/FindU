# FindU 后端开发计划

## 1. 目标

实现与 [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)、[前端接口 Contract](contracts/FRONTEND_API_CONTRACT.md) 和 [Mock 数据 Contract](contracts/MOCK_DATA_CONTRACT.md) 一致的 FastAPI 后端。

第一版以 Replay 模式为主路径：即使真实语音或 LLM 服务不可用，前端仍能通过后端 API 展示一条三轮协商轨迹、一次拒绝、一次双方 Agent 意向和真人确认等待状态。

## 2. 技术决策

- Python 3.11+、FastAPI、Pydantic、SQLAlchemy、SQLite；
- HTTP JSON 与 SSE payload 使用 `camelCase`；数据库列和内部 Python 字段可以使用 `snake_case`；
- 临时 Bearer Token 绑定参与者身份；前端传入的 participant ID 只能作为路由目标，后端必须校验归属；
- 所有 Agent 决策、状态转换、轮次和联系上限由后端执行；
- `privateReason`、私有偏好、完整转写和 Prompt 永不进入公开 API、SSE 或候选卡；
- 先完成 `REPLAY`，再接入 `LIVE` 语音与 LLM Provider。

## 3. 开发阶段

### 阶段 1：服务骨架与可测试基础

**目标**：建立可以稳定启动、测试和部署的 FastAPI 项目，不实现具体业务流程。

**实现**：

- `app/main.py`、配置模块、路由注册、CORS、统一错误包络；
- `GET /health` 和 `GET /api/v1/health`；
- `app/api`、`schemas`、`services`、`repositories`、`providers`、`models`、`tests` 目录；
- SQLite URL、数据目录和环境变量示例；
- pytest 与 FastAPI `TestClient`，覆盖健康检查和错误包络；
- 基础 README：启动命令、测试命令、环境变量说明。

**验收**：`pytest` 通过；`uvicorn app.main:app --reload` 启动后，健康检查返回 `200` 与 JSON 状态。

### 阶段 2：领域模型、数据库与身份会话

**目标**：建立所有后续 API 共用的持久化和身份边界。

**实现**：

- SQLAlchemy 模型：Activity、Participant、Profile、Agent、Conversation、Message、AgentDecision、HumanConfirmation、ParticipantSession；
- SQLite 初始化与测试隔离；
- `POST /api/v1/participants` 创建临时参与者及不可猜测 Token；
- Bearer Token 依赖注入与资源所有权校验；
- `camelCase` 请求/响应序列化；
- 预置 `act_demo` 活动。

**验收**：无法使用 Alice Token 读取或修改 Bob 的 profile；无效 Token 返回统一 `401`；不存在或无权限资源返回 `404`。

### 阶段 3：画像草稿、确认和权限过滤

**目标**：给前端提供录音前的完整接口闭环，并建立私有字段边界。

**实现**：

- `POST /participants/{id}/profile-draft`：先支持传入预设转写，返回画像草稿；
- `PUT/GET /participants/{id}/profile`：保存确认项、公开/私有/禁用权限，创建或刷新 Agent；
- 固定的本地画像提取 Adapter，后续可替换为 LLM；
- `POST /participants/{id}/recording` 接口桩和临时文件删除契约；
- 公开广播生成与字段过滤函数。

**验收**：私有推断不会出现在广播、远端 Agent 上下文或候选卡响应；禁用项不进入确认后的 Agent 上下文。

### 阶段 4：会话状态机与联系硬限制

**目标**：实现 Agent 协商的不可绕过业务规则。

**实现**：

- Conversation 状态机：`PENDING_RESPONSE`、`ACTIVE`、`PROPOSED`、`MUTUAL_AGENT_INTENT`、终态；
- 每轮为“发起 + 响应”，最多 3 轮；
- 原子新建会话事务：发起方最多 3 个、目标最多 5 个入站联系；
- 第 6 个并发联系返回 `409 TARGET_BUSY`；拒绝或超时不释放入站名额；
- 每个无序 Agent 对在一个匹配窗口只保留一条关系记录；
- Agent Action Contract 校验与私有决定存储。

**验收**：状态机单测覆盖所有合法和非法转换；并发测试证明入站计数不会超过 5；第四轮普通消息被拒绝。

### 阶段 5：Mock Loader、Replay Runtime 与 SSE

**目标**：优先完成可演示的多 Agent 协商主路径。

**实现**：

- 加载 `mock/agents.json`、`live_alice_template.json` 和两条轨迹；
- `POST /activities/{id}/runs`：一次运行一个 Agent 动作；
- 内存 `AgentScheduler`：使用 `{conversationId, expectedStatus, expectedNextActorId}` 幂等队列项；
- `GET /activities/{id}/events`：参与者过滤、事件 ID、断线重放、`sync.required`；
- `GET /conversations/{id}`、`GET /me/conversations`、`GET /participants/{id}/candidate-intents`；
- 主轨迹与拒绝轨迹的 Replay Provider。

**验收**：前端仅使用后端 Replay API 就能完整播放三轮消息、判断变化、拒绝与双向 Agent 意向；SSE 重连不重复消息。

### 阶段 6：真人确认与候选卡上限

**目标**：把 Agent 双向意向安全地交给真人。

**实现**：

- `POST /conversations/{id}/human-confirmations`；
- `GET /conversations/{id}/confirmation-status`；
- 只有 `PROPOSE + ACCEPT` 才生成候选卡；
- 双方真人 `ACCEPT` 后才进入 `CONNECTED`；任一真人 `REJECT` 进入 `HUMAN_REJECTED`；
- 每 Agent 最多 5 个 `MUTUAL_AGENT_INTENT`，超过时由该 Agent 先撤回一条未确认候选关系。

**验收**：单方 Agent 提案不能确认；单方真人确认保持等待；真人拒绝释放候选额度但不释放入站联系额度。

### 阶段 7：真实 Provider 与降级处理

**目标**：保留真实体验，同时不破坏 Replay Demo。

**实现**：

- Speech Provider Adapter：上传音频、转写、失败映射为 `PROVIDER_UNAVAILABLE`；
- LLM Provider Adapter：画像提取和 Agent Action 结构化输出；
- 一次 JSON 修复重试；
- Provider 失败时切换预设转写或 Replay 轨迹；
- 不记录原始音频、完整转写或 Token 到日志。

**验收**：外部 API 失败时前端可立即切换到预设转写或回放，服务不崩溃。

### 阶段 8：联调、测试与交付

**目标**：让前端和 Mock 数据分支可以稳定合并。

**实现**：

- 根据 `contracts/` 的 Fixture 做契约测试；
- 执行权限、状态机、限额、Replay、SSE 和真人确认测试；
- 生成 OpenAPI JSON；
- 写入本地启动、重置 Demo 数据和运行测试的 README；
- 进行手机视图实际联调。

**验收**：所有测试通过；前端按 Contract 不需要修改后端私有字段；Demo 可在真实语音与回放两条路径运行。

## 4. 文件结构

```text
app/
  __init__.py
  main.py
  api/
  models/
  schemas/
  services/
  repositories/
  providers/
  tests/
mock/
  agents.json
  live_alice_template.json
  replay_tracks/
```

## 5. 开发顺序

阶段 1 到阶段 6 是 MVP 必需路径。阶段 7 只在 Replay 已稳定后开始。任何真实模型服务都不能成为前端开发、联调或演示成功的前置条件。

每完成一个阶段：运行测试、更新 OpenAPI/Fixture、提交一次独立 Git Commit，再开始下一个阶段。

## 6. 第一阶段执行提示词

将下面提示词交给负责实现第一阶段的编码 Agent，或作为本项目后端开发的第一条任务：

```text
你是 FindU 项目的后端负责人。请在当前仓库实现“阶段 1：服务骨架与可测试基础”。

先阅读：
- SYSTEM_DESIGN.md
- contracts/FRONTEND_API_CONTRACT.md
- contracts/MOCK_DATA_CONTRACT.md

技术约束：Python 3.11+、FastAPI、Pydantic、SQLite；HTTP JSON 统一 camelCase。不要实现真实 LLM、语音、Agent 状态机、数据库业务表或前端页面；本阶段只建立后端基础设施。

需要完成：
1. 创建 app/main.py，并注册 /health 和 /api/v1/health，均返回 200 JSON，例如 {"status":"ok"}。
2. 创建 app/api、app/schemas、app/services、app/repositories、app/providers、app/models、app/tests 目录与必要的 __init__.py。
3. 创建配置模块：从环境变量读取 APP_ENV、DATABASE_URL、CORS_ORIGINS；默认 SQLite 数据库位于项目本地 data/findu.db。不要把密钥写进代码或日志。
4. 添加 CORS 中间件；开发默认仅允许 http://localhost:5173 和 http://127.0.0.1:5173，支持通过 CORS_ORIGINS 覆盖。
5. 建立统一 API 错误响应格式：{"error":{"code":"...","message":"...","requestId":"..."}}，并为 404、422 和未处理异常提供一致响应。开发环境不要向客户端返回堆栈。
6. 添加 requirements.txt 或 pyproject.toml，包含运行与测试所需依赖；提供 .env.example，且不得包含真实 Token。
7. 添加 pytest 测试，至少覆盖两个健康检查路径、未知 API 路由的错误包络、422 校验错误包络。
8. 更新 README.md，写明创建虚拟环境、安装依赖、启动服务、运行测试的命令。

验收：
- pytest 通过；
- uvicorn app.main:app --reload 能启动；
- curl http://127.0.0.1:8000/api/v1/health 返回 200；
- git diff 只包含本阶段需要的文件，不修改现有产品/接口设计文档；
- 完成后报告修改文件、测试命令及结果、任何未完成项。
```

