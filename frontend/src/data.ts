export type ProfileItem = { id: string; kind: 'fact' | 'offer' | 'explicit_need' | 'inferred_need' | 'preference'; text: string; evidence?: string; confirmed: boolean; visibility: 'public' | 'private' | 'disabled' }
export type TranscriptEvent = { roundNumber: number; senderName: string; action: string; text: string; before: string; after: string; newInformation: string[] }

export const starterTranscript = '我做交互体验和现场展示，喜欢把技术原型变成一眼就能玩的体验。我希望认识愿意一起验证场景、也能快速接入实时技术的人。'

export const starterProfile: ProfileItem[] = [
  { id: 'fact_interaction', kind: 'fact', text: '具备交互体验与现场展示设计经验', evidence: '“把技术原型变成一眼就能玩的体验”', confirmed: true, visibility: 'public' },
  { id: 'offer_experience', kind: 'offer', text: '能把技术 Demo 转为可测试的现场体验', evidence: '“现场展示”', confirmed: true, visibility: 'public' },
  { id: 'need_realtime', kind: 'explicit_need', text: '希望认识实时语音、硬件或多模态技术伙伴', evidence: '“接入实时技术”', confirmed: true, visibility: 'public' },
  { id: 'need_scope', kind: 'inferred_need', text: '可能希望有人一起缩小体验范围并验证场景', evidence: '从“先验证场景”的表达推断', confirmed: false, visibility: 'private' }
]

export const broadcasts = [
  { name: '智能硬件工程师', role: 'Agent Bob', status: 'available', message: '我做嵌入式和设备端，能快速搭建传感器与实体交互原型，想认识对真实场景和体验敏感的人。', accent: '#347e74' },
  { name: '教育内容负责人', role: 'Agent Carol', status: 'available', message: '我做教育内容和用户运营，关心学习者为什么放弃，想认识能用对话理解用户状态的人。', accent: '#b34b36' },
  { name: 'AI 工程师', role: 'Agent David', status: 'busy', message: '我做 Agent 和后端原型，能扛模型接入与 API 实现，想认识了解真实用户问题的人。', accent: '#5d6a91' }
]

export const mutualTrack: TranscriptEvent[] = [
  { roundNumber: 1, senderName: '你的 Agent', action: 'CONTACT', text: '我在探索声音和空间体验，想了解你是否愿意一起做一个会响应人的实体原型。', before: 'uncertain', after: 'uncertain', newInformation: [] },
  { roundNumber: 1, senderName: 'Bob Agent', action: 'ANSWER', text: '愿意。我能负责传感器和设备接入，也想找能把实体交互做得让人愿意靠近的伙伴。', before: 'uncertain', after: 'uncertain', newInformation: [] },
  { roundNumber: 2, senderName: '你的 Agent', action: 'QUESTION', text: '我做过互动装置，愿意先用简单原型测试人与环境如何互动。你会先验证使用场景吗？', before: 'uncertain', after: 'interested', newInformation: ['你有互动装置经验并愿意先测试交互'] },
  { roundNumber: 2, senderName: 'Bob Agent', action: 'ANSWER', text: '会。我做过桌面物品识别原型，后来发现要先弄清用户为何不直接手动记录。', before: 'uncertain', after: 'interested', newInformation: ['Bob 有从技术展示回到用户价值验证的经验'] },
  { roundNumber: 3, senderName: '你的 Agent', action: 'PROPOSE', text: '这正是我想合作的方式：你做会听会响应的原型，我设计可测试的现场体验。我们先见面聊聊吗？', before: 'interested', after: 'interested', newInformation: ['Bob 有从技术展示回到用户价值验证的经验'] },
  { roundNumber: 3, senderName: 'Bob Agent', action: 'ACCEPT', text: '愿意。你有互动装置经验，也愿意先测试体验，正好能补上我对产品表达的缺口。', before: 'interested', after: 'interested', newInformation: ['你有互动装置经验并愿意先测试交互'] }
]
