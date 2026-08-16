import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ArrowRight, Check, ChevronRight, CircleDot, Ear, Eye, LockKeyhole, Mic, Play, RotateCcw, Sparkles, Users } from 'lucide-react'
import { broadcasts, mutualTrack, starterProfile, starterTranscript, type ProfileItem } from './data'
import { confirmRemote, createRemoteParticipant, getRemoteBroadcasts, getRemoteConversations, runRemoteReplay, saveRemoteProfile, subscribeRemoteEvents } from './api'

type Screen = 'entry' | 'profile' | 'workspace'

const labels: Record<ProfileItem['kind'], string> = { fact: '事实', offer: '可提供', explicit_need: '明确需求', inferred_need: '推断需求', preference: '偏好' }

export function App() {
  const [screen, setScreen] = useState<Screen>('entry')
  const [name, setName] = useState('')
  const [transcript, setTranscript] = useState(starterTranscript)
  const [items, setItems] = useState(starterProfile)
  const [steps, setSteps] = useState(0)
  const [confirmed, setConfirmed] = useState(false)
  const [toast, setToast] = useState('')
  const [remoteMode, setRemoteMode] = useState(false)
  const [remoteConversationId, setRemoteConversationId] = useState<string | null>(null)
  const [people, setPeople] = useState(broadcasts)
  const [sseConnected, setSseConnected] = useState(false)

  const round = Math.min(3, Math.ceil(steps / 2))
  const visibleEvents = mutualTrack.slice(0, steps)
  const hasIntent = steps === mutualTrack.length
  const enabled = items.filter((item) => item.confirmed && item.visibility !== 'disabled')
  const currentInsight = useMemo(() => [...visibleEvents].reverse().find((event) => event.newInformation.length)?.newInformation[0], [visibleEvents])

  const updateItem = (id: string, changes: Partial<ProfileItem>) => setItems((list) => list.map((item) => item.id === id ? { ...item, ...changes } : item))
  const nextStep = async () => {
    if (steps < mutualTrack.length) {
      if (remoteMode) { try { await runRemoteReplay(); const conversations = await getRemoteConversations(); if (conversations[0]) setRemoteConversationId(conversations[0].id) } catch { setToast('后端暂时不可用，继续播放本地回放。') } }
      setSteps((value) => value + 1)
    } else setToast('这条协商已经完成，可以由真人决定是否见面。')
  }

  const handleEntry = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setScreen('profile'); try { await createRemoteParticipant(name, transcript); setRemoteMode(true) } catch { setRemoteMode(false) } }
  const handleProfileConfirm = async () => { if (remoteMode) { try { await saveRemoteProfile(name, enabled); const remote = await getRemoteBroadcasts(); setPeople(remote.items.map((person) => ({ name: person.displayName, role: person.agentId, status: person.contactStatus, message: person.message, accent: '#347e74' }))) } catch { setToast('已切换为本地回放模式。') } } setScreen('workspace') }
  useEffect(() => { if (screen !== 'workspace' || !remoteMode) return; setSseConnected(true); const stop = subscribeRemoteEvents(() => undefined); return () => { setSseConnected(false); stop() } }, [screen, remoteMode])

  if (screen === 'entry') return <main className="onboarding"><Topbar compact /><section className="entry-grid">
    <div className="entry-copy"><p className="eyebrow">FINDU / 活动现场版</p><h1>先让你的 Agent<br />替你开口。</h1><p>把你想做的事、擅长的事和还没说清的期待交给 Agent。它会在三轮交流里寻找值得真人见面的人。</p><div className="privacy-note"><LockKeyhole size={16} /><span>确认前，推断只属于你；确认后，只有公开项会参与交流。</span></div></div>
    <form className="entry-form" onSubmit={handleEntry}>
      <label>你希望怎么被称呼<input aria-label="姓名" required value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：小林" /></label>
      <label>用一两分钟说说你自己<textarea aria-label="自我介绍" value={transcript} onChange={(event) => setTranscript(event.target.value)} /></label>
      <div className="entry-actions"><button type="button" className="icon-text" onClick={() => setToast('当前演示使用预设转写。真实录音接口已预留。')}><Mic size={17} />录一段</button><button className="primary" type="submit">生成我的画像 <ArrowRight size={17} /></button></div>
      {toast && <p className="inline-notice">{toast}</p>}
    </form>
  </section></main>

  if (screen === 'profile') return <main className="profile-page"><Topbar compact /><section className="profile-shell"><header className="page-head"><div><p className="eyebrow">你的 Agent 画像</p><h1>确认什么可以被它带去交流</h1></div><span className="step">2 / 3</span></header><p className="transcript"><Ear size={16} /> {transcript}</p>
    <div className="profile-list">{items.map((item) => <article className={`profile-row ${item.confirmed ? 'is-confirmed' : ''}`} key={item.id}>
      <div className="item-meta"><span>{labels[item.kind]}</span><p>{item.text}</p>{item.evidence && <small>{item.evidence}</small>}</div>
      <div className="item-controls"><button aria-label={`确认 ${item.text}`} className={`circle-toggle ${item.confirmed ? 'on' : ''}`} onClick={() => updateItem(item.id, { confirmed: !item.confirmed })}><Check size={15} /></button><select aria-label={`${item.text} 的可见范围`} value={item.visibility} onChange={(event) => updateItem(item.id, { visibility: event.target.value as ProfileItem['visibility'] })}><option value="public">公开</option><option value="private">仅自己</option><option value="disabled">停用</option></select></div>
    </article>)}</div>
    <footer className="profile-footer"><span>{enabled.length} 项会进入 Agent 上下文</span><button className="primary" onClick={handleProfileConfirm}>让 Agent 开始认识人 <ArrowRight size={17} /></button></footer>
  </section></main>

  return <main className="app-shell"><Topbar compact={false} /><div className="workspace">
    <aside className="broadcast-rail"><div className="rail-title"><span>公开广播</span><b>{people.length}</b></div><p className="rail-hint">每个人的 Agent 只听得到对方明确公开的部分。</p>{people.map((person) => <article className={`person ${person.status}`} key={person.name}><div className="avatar" style={{ backgroundColor: person.accent }}>{person.name.slice(0, 1)}</div><div><div className="person-name">{person.name}<span className="presence" /></div><small>{person.role}</small><p>{person.message}</p></div></article>)}</aside>
    <section className="negotiation"><header className="negotiation-head"><div><p className="eyebrow">正在协商 / 你的 Agent × Bob Agent</p><h1>先聊价值，再决定见不见面。</h1></div><div className="turn-counter"><b>{round || 1}</b><span>/ 3 轮</span></div></header>
      <div className="track" aria-live="polite">{visibleEvents.length === 0 && <div className="empty-track"><CircleDot size={24} /><p>你的 Agent 正在阅读公开广播，准备发出第一句话。</p></div>}{visibleEvents.map((event, index) => <div className={`event ${event.senderName === '你的 Agent' ? 'self' : 'other'}`} key={`${event.roundNumber}-${index}`}><div className="event-side"><span>第 {event.roundNumber} 轮</span><strong>{event.action}</strong></div><div className="bubble"><small>{event.senderName}</small><p>{event.text}</p>{event.newInformation.map((insight) => <div className="insight" key={insight}><Sparkles size={14} /> 新信息：{insight}</div>)}</div></div>)}</div>
      <footer className="runbar"><div><span className="run-label">{hasIntent ? '双方 Agent 已达成意向' : steps ? 'Agent 正在根据上一句调整判断' : '等待 Agent 首次行动'}</span>{currentInsight && <span className="judgment">判断变化：uncertain <ChevronRight size={14} /> interested</span>}</div><div className="run-actions"><span className={`sse-state ${sseConnected ? 'connected' : ''}`}><span />{sseConnected ? '实时事件已连接' : '本地回放'}</span><button className="primary" onClick={nextStep}>{hasIntent ? '查看真人意向' : <>运行下一步 <Play size={16} /></>}</button></div></footer>
    </section>
    <aside className="intent-rail"><p className="eyebrow">候选意向</p>{hasIntent ? <article className="intent-card"><span className="status-pill"><Check size={13} /> Agent 双向意向</span><h2>和 Bob 值得真人聊聊</h2><p>你带来可测试的交互体验；他带来传感器原型与场景验证的反思。</p><dl><dt>刚确认</dt><dd>双方都重视先验证用户价值</dd></dl>{!confirmed ? <button className="primary wide" onClick={async () => { setConfirmed(true); if (remoteConversationId) try { await confirmRemote(remoteConversationId, 'ACCEPT') } catch { setToast('已在本地记录你的确认。') } }}>我愿意见面聊聊 <ArrowRight size={16} /></button> : <div className="awaiting"><Users size={17} /> 已通知对方，等待对方真人确认</div>}<button className="quiet-button" onClick={() => { setConfirmed(false); setToast('已拒绝这条候选意向。') }}>暂不继续</button></article> : <div className="intent-empty"><Eye size={23} /><p>Agent 双方明确表达意向后，候选卡会出现在这里。</p></div>}{toast && <p className="inline-notice">{toast}</p>}</aside>
  </div></main>
}

function Topbar({ compact }: { compact: boolean }) { return <header className="topbar"><a className="brand" href="#top" onClick={(event) => event.preventDefault()}><span>F</span><b>FindU</b></a>{!compact && <div className="top-status"><span className="status-dot" /> 回放模式 <button title="重新开始回放" aria-label="重新开始回放" onClick={() => window.location.reload()}><RotateCcw size={16} /></button></div>}</header> }
