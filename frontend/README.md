# FindU Frontend

移动优先的 React/Vite 黑客松活动工作台。主路径是：自我介绍 -> 画像确认 -> 公开广播 -> Agent 三轮 Replay -> 双向意向 -> 真人确认。

## Run

```bash
npm install
npm run dev
```

默认地址为 `http://127.0.0.1:5173`。生产构建使用 `npm run build`。

前端不调用语音或 LLM 供应商。没有后端时使用本地 Replay 数据；后端可用时会调用 `/api/v1` 的参与者、画像、广播、runs、会话和真人确认接口，并使用带 Bearer Token 与 `Last-Event-ID` 的 fetch-based SSE。可用 `VITE_API_BASE_URL` 覆盖 API 地址。
