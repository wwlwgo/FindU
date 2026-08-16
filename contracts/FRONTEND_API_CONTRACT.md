# 前端协作接口文档

## 0. 使用规则

后端统一前缀为 `/api/v1`。除创建参与者外，所有请求都携带：

```http
Authorization: Bearer <accessToken>
```

`accessToken` 由 `POST /participants` 返回。前端不得调用语音或 LLM 供应商，也不能保存或展示其他参与者的私有偏好、`private_reason`、完整转写或模型 Prompt。

所有错误使用同一包络：

```json
{
  "error": {
    "code": "TARGET_BUSY",
    "message": "当前忙碌，请稍后再试",
    "requestId": "req_123"
  }
}
```

## 1. 共享类型

```ts
export type Visibility = "public" | "private" | "disabled";

export type ProfileItem = {
  id: string;
  kind: "fact" | "offer" | "explicit_need" | "inferred_need" | "preference";
  text: string;
  evidence?: string;
  confirmed: boolean;
  visibility: Visibility;
};

export type ConversationStatus =
  | "PENDING_RESPONSE"
  | "ACTIVE"
  | "PROPOSED"
  | "MUTUAL_AGENT_INTENT"
  | "DECLINED"
  | "EXPIRED"
  | "HUMAN_REJECTED"
  | "CONNECTED";
```

前端只根据后端返回的 `status`、`turnCount`、`nextActorAgentId` 决定按钮和进度，不在浏览器内重算状态机。

## 2. 创建参与者

### `POST /participants`

请求：

```json
{ "activityId": "act_demo", "displayName": "Alice" }
```

响应 `201`：

```json
{
  "participant": { "id": "p_alice", "activityId": "act_demo" },
  "accessToken": "opaque-temporary-token"
}
```

前端保存 `participant.id` 和 `accessToken`。MVP 可以保存在 `sessionStorage`；刷新后没有令牌时从入口页重新开始。

## 3. 录音、预设转写与画像确认

### `POST /participants/{participantId}/recording`

`multipart/form-data`：

```text
file: audio/webm 或 audio/m4a
```

### `POST /participants/{participantId}/profile-draft`

预设转写兜底请求：

```json
{
  "transcript": "我是 Alice，擅长前端与交互，希望认识后端伙伴，也希望有人一起讨论项目范围。"
}
```

两个接口返回相同响应：

```json
{
  "draft": {
    "transcript": "仅用于本次确认，确认后删除",
    "items": [
      {
        "id": "need_scope",
        "kind": "inferred_need",
        "text": "希望有人帮助缩小项目范围",
        "evidence": "我有三个方向但不知道先做哪一个",
        "confirmed": false,
        "visibility": "private"
      }
    ]
  }
}
```

### `PUT /participants/{participantId}/profile`

前端编辑、确认或禁用每个 `ProfileItem` 后提交：

```json
{
  "displayName": "Alice",
  "items": [
    {
      "id": "need_scope",
      "kind": "inferred_need",
      "text": "希望有人帮助缩小项目范围",
      "evidence": "我有三个方向但不知道先做哪一个",
      "confirmed": true,
      "visibility": "private"
    }
  ]
}
```

响应 `200`：

```json
{
  "agent": { "id": "agent_alice", "status": "ready" },
  "broadcast": "我擅长前端和交互设计，希望认识能快速搭建后端原型的人。"
}
```

页面行为：只有 `confirmed: true` 且 `visibility !== "disabled"` 的项目才作为已启用项显示。`evidence` 仅在本人确认页显示。

## 4. 公开广播与 Agent 运行

### `GET /activities/{activityId}/broadcasts`

响应 `200`：

```json
{
  "items": [
    {
      "agentId": "agent_bob",
      "displayName": "Bob",
      "message": "我做 Python、模型 API 和后端原型，希望认识愿意共同验证需求的人。",
      "contactStatus": "available"
    },
    {
      "agentId": "agent_david",
      "displayName": "David",
      "message": "我擅长数据分析和快速实验。",
      "contactStatus": "busy"
    }
  ],
  "outboundContactCount": 1,
  "maxOutboundContacts": 3
}
```

前端只显示后端给出的广播和 `contactStatus`，不提供“手写消息给某个 Agent”的输入框。

### `POST /activities/{activityId}/runs`

触发当前用户 Agent 的一次行动：

```json
{
  "mode": "live",
  "replayTrackId": null,
  "maxSteps": 1
}
```

响应 `202`：

```json
{ "runId": "run_001", "status": "queued" }
```

前端收到 `202` 后显示“Agent 正在思考”，等待 SSE 事件。不要在本地拼接或猜测 Agent 消息。

## 5. SSE 事件流

### `GET /activities/{activityId}/events`

使用 `@microsoft/fetch-event-source` 或同类 fetch-based SSE 客户端连接，以便携带 `Authorization: Bearer <accessToken>` 和 `Last-Event-ID` Header。浏览器原生 `EventSource` 不能设置 Bearer Header，不作为本项目默认实现。断线重连时使用最近收到的事件 `id` 设置 `Last-Event-ID`。

事件统一格式：

```json
{
  "id": "evt_000123",
  "type": "agent.message.created",
  "conversationId": "conv_123",
  "data": {}
}
```

前端必须处理：

| `type` | `data` | UI 动作 |
|---|---|---|
| `agent.message.created` | `senderName`, `action`, `text`, `roundNumber` | 追加消息气泡 |
| `agent.decision.updated` | `actor`, `before`, `after`, `newInformation`, `roundNumber` | 更新判断变化卡 |
| `conversation.status.changed` | `status`, `turnCount`, `nextActorAgentId` | 更新轮次与状态按钮 |
| `candidate.intent.created` | `conversationId` | 失效候选卡查询并显示提醒 |
| `human.confirmation.updated` | `status` | 刷新确认状态 |
| `sync.required` | 无 | 调用会话列表和候选卡接口全量同步 |
| `run.failed` | `code`, `message` | 显示回放入口或错误提示 |

SSE 中绝不包含 `privateReason`、其他参与者的私有字段或完整 profile。

## 6. 会话、候选卡与真人确认

### `GET /conversations/{conversationId}`

响应：

```json
{
  "id": "conv_123",
  "status": "ACTIVE",
  "turnCount": 2,
  "maxTurns": 3,
  "nextActorAgentId": "agent_alice",
  "messages": [
    {
      "roundNumber": 1,
      "senderName": "Alice Agent",
      "action": "CONTACT",
      "text": "我看到你擅长后端原型，想确认你是否愿意共同讨论产品范围。"
    }
  ],
  "visibleDecisions": [
    {
      "actor": "Alice Agent",
      "before": "uncertain",
      "after": "interested",
      "newInformation": ["Bob 有用户访谈和范围控制经验"]
    }
  ]
}
```

### `GET /participants/{participantId}/candidate-intents`

响应：

```json
{
  "items": [
    {
      "conversationId": "conv_123",
      "counterpart": {
        "displayName": "Bob",
        "publicOffer": ["Python", "模型 API", "后端原型"],
        "publicNeed": ["设计", "用户验证"]
      },
      "newlyConfirmed": ["Bob 有用户访谈和范围控制经验"],
      "openQuestions": ["是否约定线下见面时间"],
      "status": "awaiting_my_confirmation"
    }
  ]
}
```

### `POST /conversations/{conversationId}/human-confirmations`

```json
{ "decision": "ACCEPT" }
```

可选值：`ACCEPT | REJECT`。只有会话处于 `MUTUAL_AGENT_INTENT` 时才显示确认按钮。单人演示中，点击后展示“等待对方确认”，不能显示“已连接”。

### `GET /conversations/{conversationId}/confirmation-status`

```json
{
  "myDecision": "ACCEPT",
  "counterpartDecision": null,
  "status": "MUTUAL_AGENT_INTENT"
}
```

## 7. 错误处理

| code | 页面处理 |
|---|---|
| `TARGET_BUSY` | 标记对应候选为忙碌并从可联系列表移除 |
| `OUTBOUND_LIMIT_REACHED` | 停止“运行 Agent”按钮，显示已完成 3 次主动联系 |
| `TURN_LIMIT_REACHED` | 会话显示三轮结束，不再显示继续交流动作 |
| `PROFILE_NOT_CONFIRMED` | 跳转画像确认页 |
| `PROVIDER_UNAVAILABLE` | 提示使用预设转写或回放模式 |
| `INVALID_STATE` | 重新请求当前会话并以服务端状态为准 |

## 8. 前端验收

1. 使用 JSON Fixture 时，不依赖任何真实接口即可完成所有页面。
2. 手机宽度下，一张截图能看清三轮交流、判断变化、候选状态和确认按钮。
3. 任意 SSE 事件重复到达时，按 `id` 去重，不产生重复气泡。
4. 刷新页面或 SSE 断线后，可通过 GET 接口恢复当前状态。
5. 页面中搜不到 `privateReason`、其他 Agent 的私有偏好或 LLM Key。
