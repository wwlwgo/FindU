import type { ProfileItem } from './data'

const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')
type Session = { participantId: string; accessToken: string }
export type RemoteConversation = { id: string; status: string; turnCount: number; messages: Array<{ roundNumber: number; senderName: string; action: string; text: string }> }

let session: Session | null = (() => { try { return JSON.parse(sessionStorage.getItem('findu-session') || 'null') } catch { return null } })()

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${base}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(session ? { Authorization: `Bearer ${session.accessToken}` } : {}), ...(init.headers || {}) } })
  if (!response.ok) throw new Error(`API ${response.status}`)
  return response.json() as Promise<T>
}

export async function createRemoteParticipant(displayName: string, transcript: string) {
  const created = await request<{ participant: { id: string }; accessToken: string }>('/participants', { method: 'POST', body: JSON.stringify({ activityId: 'act_demo', displayName }) })
  session = { participantId: created.participant.id, accessToken: created.accessToken }
  sessionStorage.setItem('findu-session', JSON.stringify(session))
  await request(`/participants/${session.participantId}/profile-draft`, { method: 'POST', body: JSON.stringify({ transcript }) })
  return session
}
export async function saveRemoteProfile(displayName: string, items: ProfileItem[]) { if (!session) return; return request(`/participants/${session.participantId}/profile`, { method: 'PUT', body: JSON.stringify({ displayName, items }) }) }

export async function getRemoteBroadcasts() { return request<{ items: Array<{ agentId: string; displayName: string; message: string; contactStatus: 'available' | 'busy' }>; outboundContactCount: number; maxOutboundContacts: number }>('/activities/act_demo/broadcasts') }
export async function runRemoteReplay() { if (!session) return; await request('/activities/act_demo/runs', { method: 'POST', body: JSON.stringify({ mode: 'replay', replayTrackId: 'alice_bob_mutual_intent', maxSteps: 1 }) } ) }
export async function getRemoteConversations() { return request<RemoteConversation[]>('/me/conversations') }
export async function confirmRemote(conversationId: string, decision: 'ACCEPT' | 'REJECT') { return request(`/conversations/${conversationId}/human-confirmations`, { method: 'POST', body: JSON.stringify({ decision }) }) }

export function subscribeRemoteEvents(onEvent: (event: { type: string; data: Record<string, unknown> }) => void) {
  if (!session) return () => undefined
  const controller = new AbortController()
  fetch(`${base}/activities/act_demo/events`, { headers: { Authorization: `Bearer ${session.accessToken}`, Accept: 'text/event-stream', ...(sessionStorage.getItem('findu-last-event-id') ? { 'Last-Event-ID': sessionStorage.getItem('findu-last-event-id')! } : {}) }, signal: controller.signal }).then(async (response) => {
    if (!response.body) return
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
    while (!controller.signal.aborted) { const chunk = await reader.read(); if (chunk.done) break; buffer += decoder.decode(chunk.value, { stream: true }); const frames = buffer.split('\n\n'); buffer = frames.pop() || ''; for (const frame of frames) { const id = frame.split('\n').find((line) => line.startsWith('id: '))?.slice(4); if (id) sessionStorage.setItem('findu-last-event-id', id); const data = frame.split('\n').find((line) => line.startsWith('data: '))?.slice(6); if (data) { try { const parsed = JSON.parse(data); onEvent({ type: parsed.type, data: parsed.data || {} }) } catch { /* ignore malformed SSE frame */ } } } }
  }).catch(() => undefined)
  return () => controller.abort()
}
