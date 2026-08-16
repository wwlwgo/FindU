# Agent Mock 数据协作接口文档

## 0. 交付目标

请准备可被后端直接加载的 4 名预设 Agent 和至少两条回放轨迹：

1. 一条三轮协商后形成双方 Agent 意向的主轨迹；
2. 一条礼貌拒绝轨迹；
3. 每个 Agent 都有公开广播、公开画像、私有偏好和独立决策理由；
4. 所有数据严格区分“可发给前端/其他 Agent”的公开字段和“仅后端可用”的私有字段。

建议文件结构：

```text
mock/
  agents.json
  live_alice_template.json
  replay_tracks/
    alice_bob_mutual_intent.json
    alice_carol_decline.json
```

文件使用 UTF-8 JSON，不写注释，不放任何真实个人隐私或 API Key。

## 1. 共享枚举

```text
provider_mode: LIVE | SEEDED | REPLAY
visibility: public | private | disabled
action: CONTACT | QUESTION | ANSWER | CLARIFY | PROPOSE | ACCEPT | DECLINE | WAIT
decision: pass | uncertain | interested
conversation_status: PENDING_RESPONSE | ACTIVE | PROPOSED |
  MUTUAL_AGENT_INTENT | DECLINED | EXPIRED | HUMAN_REJECTED | CONNECTED
```

一轮由“发起动作 + 对方响应”组成；发起与响应使用相同的 `roundNumber`。最多 3 轮。

## 2. `agents.json` 格式

```json
{
  "activityId": "act_demo",
  "agents": [
    {
      "agentId": "agent_bob",
      "participantId": "p_bob",
      "displayName": "Bob",
      "providerMode": "SEEDED",
      "publicProfile": {
        "facts": ["Python", "后端服务", "模型 API"],
        "offers": ["搭建后端原型", "接入模型 API"],
        "needs": ["交互设计", "早期用户验证"]
      },
      "broadcast": "我做 Python、模型 API 和后端原型，希望认识愿意共同验证需求的人。",
      "privatePreferences": [
        {
          "text": "不想只接需求，希望队友愿意一起验证产品范围。",
          "evidence": "主人确认",
          "visibility": "private"
        }
      ],
      "shareableContext": [
        {
          "text": "上次黑客松中负责过用户访谈和功能范围取舍。",
          "visibility": "public",
          "broadcasted": false
        }
      ],
      "limits": {
        "maxOutboundContacts": 3,
        "maxCandidateIntents": 5
      }
    }
  ]
}
```

字段说明：

| 字段 | 后端用途 | 可发到前端或其他 Agent？ |
|---|---|---|
| `publicProfile` | 生成广播、候选卡和远端 Agent 可见上下文 | 可以 |
| `broadcast` | 广播页 | 可以 |
| `shareableContext` | 在相关问题出现时供本 Agent 回答 | `visibility: public` 的 `text` 可以在对话中出现；不能自动全部展示 |
| `privatePreferences` | 本 Agent 自主判断与选择问题 | 不可以 |
| `evidence` | 主人侧或后端调试 | 不可以发给其他 Agent |

`shareableContext` 用于制造“初始广播中没有、但协商后获得的新信息”。它必须标为 `public`，否则 Agent 不得在对话中披露。

另外提供 `live_alice_template.json`，供回放模式建立 `agent_alice`。格式只需要一名 LIVE Agent 的 `publicProfile`、`privatePreferences` 和 `broadcast`，与 `agents.json` 中的单个 Agent 对象相同；它代表预设演示输入，不替代现场用户真实录音生成的画像。

## 3. 四名预设 Agent 建议角色

| Agent | 公开 Offer | 公开 Need | 私有目标 / 预期作用 |
|---|---|---|---|
| Bob | Python、模型 API、后端原型 | 设计、用户验证 | 主轨迹对象；隐藏在广播外的可分享经历是用户访谈与范围控制 |
| Carol | 产品策略、用户研究 | 技术原型 | 拒绝轨迹对象；可投入时间不足或工作节奏不兼容 |
| David | 数据分析、实验设计 | 前端可视化 | 可显示“当前忙碌”或作为第三候选 |
| Emma | 品牌、演示叙事、商业表达 | 技术伙伴 | 丰富广播池，避免所有画像同质化 |

不要让四人只是在技能上互补。至少让每个 Agent 有一个明确问题、一个可公开 Offer 和一个不可公开的合作底线，保证他们会作出不同决定。

## 4. 主轨迹：`alice_bob_mutual_intent.json`

此轨迹必须刚好 3 轮，并证明双方 Agent 都因新增信息更新判断。

```json
{
  "trackId": "alice_bob_mutual_intent",
  "conversationId": "conv_alice_bob",
  "participants": ["agent_alice", "agent_bob"],
  "initialStatus": "PENDING_RESPONSE",
  "events": [
    {
      "roundNumber": 1,
      "senderAgentId": "agent_alice",
      "action": "CONTACT",
      "publicMessage": "我看到你擅长后端原型，想确认你是否愿意一起讨论产品范围。",
      "decisionBefore": "uncertain",
      "decisionAfter": "uncertain",
      "missingInformation": ["Bob 是否愿意参与产品判断"],
      "newInformation": [],
      "nextStatus": "PENDING_RESPONSE"
    },
    {
      "roundNumber": 1,
      "senderAgentId": "agent_bob",
      "action": "ANSWER",
      "publicMessage": "我愿意一起讨论范围，也希望设计伙伴愿意参与早期用户验证。",
      "decisionBefore": "uncertain",
      "decisionAfter": "uncertain",
      "missingInformation": ["Alice 是否愿意先验证需求"],
      "newInformation": [],
      "nextStatus": "ACTIVE"
    },
    {
      "roundNumber": 2,
      "senderAgentId": "agent_alice",
      "action": "QUESTION",
      "publicMessage": "你以前做过用户访谈或功能范围取舍吗？",
      "decisionBefore": "uncertain",
      "decisionAfter": "uncertain",
      "missingInformation": ["Bob 的产品协作经验"],
      "newInformation": [],
      "nextStatus": "PENDING_RESPONSE"
    },
    {
      "roundNumber": 2,
      "senderAgentId": "agent_bob",
      "action": "ANSWER",
      "publicMessage": "上次黑客松中我负责过用户访谈和功能范围取舍，只是广播里主要介绍了技术能力。",
      "decisionBefore": "uncertain",
      "decisionAfter": "uncertain",
      "missingInformation": [],
      "newInformation": ["Bob 有用户访谈和范围控制经验"],
      "nextStatus": "ACTIVE"
    },
    {
      "roundNumber": 3,
      "senderAgentId": "agent_alice",
      "action": "PROPOSE",
      "publicMessage": "这解决了我对产品协作的担心。我可以负责前端和交互，并在第一小时做快速用户验证。我们值得见面聊聊吗？",
      "decisionBefore": "uncertain",
      "decisionAfter": "interested",
      "missingInformation": [],
      "newInformation": ["Bob 有用户访谈和范围控制经验"],
      "nextStatus": "PROPOSED"
    },
    {
      "roundNumber": 3,
      "senderAgentId": "agent_bob",
      "action": "ACCEPT",
      "publicMessage": "愿意。你愿意先验证需求正好符合我希望共同做产品判断的目标。",
      "decisionBefore": "uncertain",
      "decisionAfter": "interested",
      "missingInformation": [],
      "newInformation": ["Alice 愿意先进行快速用户验证"],
      "nextStatus": "MUTUAL_AGENT_INTENT"
    }
  ]
}
```

注意：`publicMessage` 中只能出现 Bob 的 `publicProfile` 或 `shareableContext` 中标记为 `public` 的事实。`privateReason` 可以由后端另存，但不能放进轨迹的公开事件。

## 5. 拒绝轨迹：`alice_carol_decline.json`

拒绝必须礼貌且可解释，不要写成能力高低评价。示例：

```json
{
  "trackId": "alice_carol_decline",
  "conversationId": "conv_alice_carol",
  "participants": ["agent_alice", "agent_carol"],
  "initialStatus": "PENDING_RESPONSE",
  "events": [
    {
      "roundNumber": 1,
      "senderAgentId": "agent_carol",
      "action": "CONTACT",
      "publicMessage": "我在做产品策略和用户研究，想了解你是否希望先花时间验证方向。",
      "decisionBefore": "uncertain",
      "decisionAfter": "uncertain",
      "missingInformation": ["Alice 的活动节奏"],
      "newInformation": [],
      "nextStatus": "PENDING_RESPONSE"
    },
    {
      "roundNumber": 1,
      "senderAgentId": "agent_alice",
      "action": "DECLINE",
      "publicMessage": "谢谢联系。这次我希望在前一小时完成原型，当前节奏可能不适合继续占用你的时间。祝你的方向进展顺利。",
      "decisionBefore": "uncertain",
      "decisionAfter": "pass",
      "missingInformation": [],
      "newInformation": ["双方的前期节奏不同"],
      "nextStatus": "DECLINED"
    }
  ]
}
```

## 6. 数据校验清单

提交前请检查：

1. `agentId`、`participantId`、`conversationId` 和 `trackId` 全局唯一且互相引用正确。
2. 一条轨迹中每轮恰好有一条发起消息和一条回应消息；拒绝可以在第一轮结束。
3. `roundNumber` 只能是 `1`、`2`、`3`，且不递减。
4. `PROPOSE` 只能在 `ACTIVE` 后出现；`ACCEPT` 只能回应 `PROPOSE`；最终 `MUTUAL_AGENT_INTENT` 必须由 `PROPOSE + ACCEPT` 形成。
5. 主轨迹至少有一条 `newInformation` 不存在于对方的广播文本中。
6. 每名 Agent 至少有一个私有偏好，但没有任何私有偏好出现在 `broadcast` 或 `publicMessage` 中。
7. 拒绝理由描述协作边界、时间或目标，不评价人格、性别、年龄、学校、照片或其他无关属性。
8. 所有文本可在手机屏幕上阅读：单条 `publicMessage` 建议不超过 80 个中文字符。

## 7. 交付方式

1. 新建分支，例如 `data/agent-mock-fixtures`。
2. 提交 `mock/agents.json` 和两条 `mock/replay_tracks/*.json`。
3. 在 PR 描述中写明：主轨迹的“新增信息”是什么、双方各自在哪一步改变判断、拒绝轨迹为何结束。
4. 后端加载 JSON 后会执行 schema 校验；字段不符合本文档时不进入主分支。
