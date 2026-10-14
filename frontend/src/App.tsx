import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

type Ticket = {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  state: string
  resolved: boolean
  notes: string | null
  created_at: string
}

type AuditEvent = {
  timestamp: string
  run_id: string
  agent: string
  step: number
  event: string
  action: string
  input_summary: string
  output_summary: string
  delegated_to: string | null
  agent_said: string
  tool: string | null
  tools_used: string[]
}

type TeamRun = {
  run_id: string
  output: string
  rounds: number
  model: string
}

type ApprovalTarget = {
  kind: 'invoice' | 'lease' | 'purchase'
  refId: number
  label: string
  amount?: number
}

type IconName = 'grid' | 'ticket' | 'pulse' | 'wallet' | 'settings' | 'arrow' | 'spark' | 'play' | 'check' | 'refresh' | 'close'

// Keep the local backend explicit so the board works when Vite serves the page
// from port 5173. Deployments can still override it with VITE_API_BASE_URL.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

const AGENTS = [
  { key: 'boss', name: 'Boss', role: 'Orchestrator', color: 'coral' },
  { key: 'inventory', name: 'Inventory', role: 'Stock & vendors', color: 'blue' },
  { key: 'accounting', name: 'Accounting', role: 'Cash & invoices', color: 'gold' },
  { key: 'facilities', name: 'Facilities', role: 'Lease & rent', color: 'mint' },
  { key: 'customer_service', name: 'Customer Service', role: 'Board drafts', color: 'violet' },
] as const

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
  })
  const body = (await response.json()) as T & { detail?: string }
  if (!response.ok) {
    throw new Error(body.detail ?? `Request failed (${response.status})`)
  }
  return body
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    ticket: <><path d="M4 7a2 2 0 0 0 0-4h16a2 2 0 0 0 0 4v10a2 2 0 0 0 0 4H4a2 2 0 0 0 0-4Z" /><path d="M13 3v18" strokeDasharray="2 3" /></>,
    pulse: <><path d="M3 12h4l2.2-6 4.1 12 2.1-6H21" /><circle cx="9.2" cy="6" r="1" /></>,
    wallet: <><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H20v16H6.5A2.5 2.5 0 0 1 4 17.5Z" /><path d="M4 7h14.5A2.5 2.5 0 0 1 21 9.5V15h-5a2.5 2.5 0 0 1 0-5h5" /><circle cx="16" cy="12.5" r=".8" fill="currentColor" stroke="none" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2.6V20a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1A1.7 1.7 0 0 0 8 15a1.7 1.7 0 0 0-1.6-1H6v-2.6h.4A1.7 1.7 0 0 0 8 10a1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2H15V5a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2V14H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    spark: <><path d="m12 3-1.4 5.6L5 10l5.6 1.4L12 17l1.4-5.6L19 10l-5.6-1.4Z" /><path d="m19 16-.6 2.4L16 19l2.4.6L19 22l.6-2.4L22 19l-2.4-.6Z" /></>,
    play: <path d="m8 5 11 7-11 7Z" fill="currentColor" stroke="none" />,
    check: <path d="m5 12 4.2 4.2L19 6.5" />,
    refresh: <><path d="M20 11a8 8 0 0 0-14.7-3L3 11" /><path d="M3 5v6h6" /><path d="M4 13a8 8 0 0 0 14.7 3L21 13" /><path d="M21 19v-6h-6" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  }
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

function shortType(type: string) {
  return type.replaceAll('_', ' ')
}

function timeLabel(timestamp: string) {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return 'recently'
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedId, setSelectedId] = useState(101)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [balance, setBalance] = useState<number | null>(null)
  const [run, setRun] = useState<TeamRun | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [approver, setApprover] = useState('')
  const [purchaseAmount, setPurchaseAmount] = useState('')
  const [approving, setApproving] = useState(false)

  const selectedTicket = tickets.find((ticket) => ticket.id === selectedId) ?? null

  const refreshTickets = useCallback(async () => {
    const response = await apiFetch<{ tickets: Ticket[] }>('/api/tickets')
    setTickets(response.tickets)
    if (!response.tickets.some((ticket) => ticket.id === selectedId) && response.tickets[0]) {
      setSelectedId(response.tickets[0].id)
    }
  }, [selectedId])

  const refreshBalance = useCallback(async () => {
    const response = await apiFetch<{ balance: number }>('/api/cash/checking')
    setBalance(response.balance)
  }, [])

  const refreshEvents = useCallback(async () => {
    const response = await apiFetch<{ events: AuditEvent[] }>('/api/events?limit=100')
    setEvents(response.events)
  }, [])

  const refreshBoard = useCallback(async () => {
    try {
      setError('')
      await Promise.all([refreshTickets(), refreshBalance(), refreshEvents()])
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not reach the desk backend.')
    }
  }, [refreshBalance, refreshEvents, refreshTickets])

  useEffect(() => { void refreshBoard() }, [refreshBoard])

  useEffect(() => {
    if (!running) return undefined
    const timer = window.setInterval(() => { void refreshEvents() }, 1200)
    return () => window.clearInterval(timer)
  }, [refreshEvents, running])

  const selectedEvents = useMemo(() => {
    if (!selectedTicket) return events
    return events.filter((event) => {
      const haystack = `${event.input_summary} ${event.output_summary}`
      return !haystack || haystack.includes(String(selectedTicket.id)) || event.run_id === run?.run_id
    })
  }, [events, run?.run_id, selectedTicket])

  const latestByAgent = useMemo(() => {
    const latest = new Map<string, AuditEvent>()
    selectedEvents.forEach((event) => latest.set(event.agent, event))
    return latest
  }, [selectedEvents])

  const approvalTarget = useMemo<ApprovalTarget | null>(() => {
    if (!selectedTicket) return null
    if (selectedTicket.invoice_id) return { kind: 'invoice', refId: selectedTicket.invoice_id, label: `Invoice ${selectedTicket.invoice_id}` }
    if (selectedTicket.lease_id) return { kind: 'lease', refId: selectedTicket.lease_id, label: `Lease ${selectedTicket.lease_id}` }
    if (selectedTicket.type === 'price_override') return { kind: 'purchase', refId: selectedTicket.id, label: 'Purchase request' }
    return null
  }, [selectedTicket])

  async function runSelectedTicket() {
    if (!selectedTicket || running) return
    setRunning(true)
    setRun(null)
    setNotice('')
    setError('')
    try {
      const response = await apiFetch<{ ticket: Ticket; run: TeamRun; events: AuditEvent[] }>(`/api/tickets/${selectedTicket.id}/run`, { method: 'POST' })
      setRun(response.run)
      setEvents(response.events)
      setTickets((current) => current.map((ticket) => ticket.id === selectedTicket.id ? { ...ticket, status: 'resolved', state: 'resolved', resolved: true } : ticket))
      setNotice(`Ticket ${selectedTicket.id} is ready for review.`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The team run failed.')
    } finally {
      setRunning(false)
    }
  }

  async function approveSelectedPayment() {
    if (!approvalTarget || !approver.trim() || approving) return
    setApproving(true)
    setError('')
    setNotice('')
    try {
      const payload: Record<string, string | number> = {
        kind: approvalTarget.kind,
        ref_id: approvalTarget.refId,
        approved_by: approver.trim(),
      }
      if (approvalTarget.kind === 'purchase') payload.amount = Number(purchaseAmount)
      const response = await apiFetch<{ balance: number }>('/api/payments/approve', { method: 'POST', body: JSON.stringify(payload) })
      setBalance(response.balance)
      setNotice(`Approved. Checking now has ${formatMoney(response.balance)} available.`)
      setApprover('')
      setPurchaseAmount('')
      await refreshEvents()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Payment approval failed.')
    } finally {
      setApproving(false)
    }
  }

  async function resetDesk() {
    setError('')
    setNotice('')
    try {
      const response = await apiFetch<{ tickets: Ticket[]; cash: { balance: number } }>('/api/reset', { method: 'POST' })
      setTickets(response.tickets)
      setBalance(response.cash.balance)
      setRun(null)
      setEvents([])
      setNotice('Desk reset to the original baseline.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not reset the desk.')
    }
  }

  const openCount = tickets.filter((ticket) => !ticket.resolved).length
  const resolvedCount = tickets.filter((ticket) => ticket.resolved).length

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><div className="brand-mark"><Icon name="spark" size={19} /></div><div><strong>Campus</strong><span>Customs</span></div></div>
        <div className="sidebar-caption">OPERATIONS DESK</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className="nav-item active"><Icon name="grid" /> <span>Live board</span><span className="nav-dot" /></button>
          <button className="nav-item"><Icon name="ticket" /> <span>Tickets</span><span className="nav-count">{tickets.length || '—'}</span></button>
          <button className="nav-item"><Icon name="pulse" /> <span>Agent activity</span></button>
          <button className="nav-item"><Icon name="wallet" /> <span>Cash control</span></button>
        </nav>
        <div className="sidebar-spacer" />
        <div className="desk-health"><div className="health-heading"><span className="online-dot" /> Backend online</div><p>FastAPI desk routes are ready for the next handoff.</p><button className="quiet-button" onClick={() => void refreshBoard()}><Icon name="refresh" size={14} /> Refresh desk</button></div>
        <div className="sidebar-foot"><div className="avatar">IC</div><div><strong>Ishan</strong><span>Desk operator</span></div><Icon name="settings" size={16} /></div>
      </aside>

      <main className="main-content">
        <header className="topbar"><div className="crumb"><span>Operations</span><Icon name="arrow" size={13} /><strong>Live board</strong></div><div className="top-actions"><span className="live-pill"><span className="pulse-dot" /> Live sync</span><button className="outline-button" onClick={() => void resetDesk()}><Icon name="refresh" size={15} /> Reset desk</button></div></header>

        <section className="hero"><div><p className="eyebrow">GOOD AFTERNOON, ISHAN <span>✦</span></p><h1>A calmer way to run<br /><em>the desk.</em></h1><p className="hero-copy">Your agents are ready to turn open requests into clear next steps, with every decision visible.</p></div><div className="hero-scribble"><span>Today’s focus</span><strong>{selectedTicket ? `Ticket ${selectedTicket.id}` : 'Pick a ticket'}</strong><small>{selectedTicket?.subject ?? 'Waiting for the backend'}</small></div></section>

        {error && <div className="alert error-alert"><Icon name="close" size={16} /><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error"><Icon name="close" size={15} /></button></div>}
        {notice && <div className="alert success-alert"><Icon name="check" size={16} /><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss notice"><Icon name="close" size={15} /></button></div>}

        <section className="stats-row" aria-label="Desk summary">
          <div className="stat-card"><div className="stat-icon coral"><Icon name="ticket" /></div><div><span>Open tickets</span><strong>{openCount}</strong><small><b>{resolvedCount}</b> resolved this session</small></div></div>
          <div className="stat-card"><div className="stat-icon blue"><Icon name="wallet" /></div><div><span>Checking balance</span><strong>{balance === null ? '—' : formatMoney(balance)}</strong><small><b className="up-dot">●</b> Live from cash_accounts</small></div></div>
          <div className="stat-card"><div className="stat-icon violet"><Icon name="pulse" /></div><div><span>Agent crew</span><strong>05</strong><small><b>All connected</b> via MCP</small></div></div>
        </section>

        <section className="board-grid">
          <div className="panel queue-panel"><div className="panel-heading"><div><p className="section-kicker">INBOX</p><h2>Ticket queue</h2></div><span className="tiny-count">{tickets.length} requests</span></div><p className="panel-subtitle">Choose a request to brief the team.</p><div className="ticket-list">{tickets.map((ticket) => <button key={ticket.id} className={`ticket-row ${ticket.id === selectedId ? 'selected' : ''}`} onClick={() => { setSelectedId(ticket.id); setRun(null); setNotice('') }}><div className={`ticket-glyph ${ticket.id === 101 ? 'tee' : ticket.id === 102 ? 'rent' : 'hoodie'}`}>{ticket.id === 102 ? '⌂' : ticket.id === 103 ? '◆' : '✦'}</div><div className="ticket-row-copy"><div className="ticket-row-top"><span>#{ticket.id}</span><span className={`status-mini ${ticket.resolved ? 'resolved' : ''}`}>{ticket.resolved ? 'Resolved' : 'Open'}</span></div><strong>{ticket.subject}</strong><small>{ticket.requester}</small></div><Icon name="arrow" size={16} /></button>)}</div><div className="queue-footer"><span className="online-dot" /> All requests synced <span>·</span> {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</div></div>

          <div className="panel detail-panel"><div className="detail-top"><div><p className="section-kicker">SELECTED REQUEST</p><div className="ticket-title-line"><h2>{selectedTicket ? selectedTicket.subject : 'Select a ticket'}</h2>{selectedTicket && <span className={`status-badge ${selectedTicket.resolved ? 'resolved' : ''}`}><span /> {selectedTicket.resolved ? 'Resolved' : 'Open'}</span>}</div><p className="detail-requester">{selectedTicket ? <><span className="id-chip">#{selectedTicket.id}</span> {selectedTicket.requester} <span className="middot">·</span> {shortType(selectedTicket.type)}</> : 'The selected ticket will appear here.'}</p></div><button className="run-button" disabled={!selectedTicket || running} onClick={() => void runSelectedTicket()}>{running ? <><span className="spinner" /> Team is working</> : <><Icon name="play" size={15} /> Run agent team</>}</button></div>
            {selectedTicket && <div className="ticket-facts"><div><span>Request</span><strong>{selectedTicket.sku ? `${selectedTicket.sku}${selectedTicket.size ? ` · size ${selectedTicket.size}` : ''}` : 'Shop operations'}</strong></div><div><span>Quantity</span><strong>{selectedTicket.qty ?? '—'}</strong></div><div><span>Created</span><strong>{new Date(selectedTicket.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</strong></div></div>}
            <div className="agent-section-heading"><div><p className="section-kicker">TEAM PULSE</p><h3>Who’s on it</h3></div>{running && <span className="working-label"><span className="pulse-dot" /> Live now</span>}</div><div className="agent-rail">{AGENTS.map((agent) => { const latest = latestByAgent.get(agent.key); const active = running && latest?.event !== 'loop_complete'; const state = running ? (latest ? 'Working' : 'Queued') : (latest ? 'Ready' : 'Standby'); return <div className={`agent-card ${active ? 'is-active' : ''}`} key={agent.key}><div className={`agent-avatar ${agent.color}`}>{agent.name.split(' ').map((part) => part[0]).join('')}</div><div className="agent-card-body"><div className="agent-name-line"><strong>{agent.name}</strong><span className={`agent-state ${active ? 'active' : ''}`}><i />{state}</span></div><small>{agent.role}</small><p>{latest?.agent_said || (running ? 'Waiting for a focused handoff…' : 'Ready when called.')}</p>{latest?.tool && <span className="tool-chip"><Icon name="spark" size={11} /> {latest.tool}</span>}</div></div> })}</div>
            <div className="summary-card"><div className="summary-icon"><Icon name="spark" size={17} /></div><div><p className="section-kicker">TEAM SUMMARY</p><h3>{run ? 'Run complete · ready to review' : 'What will happen next'}</h3><p>{run?.output || (selectedTicket ? 'The Boss will call only the specialists this request needs, then return a board-ready plan.' : 'Pick a request from the queue to see its plan.')}</p></div></div>
          </div>
        </section>

        <section className="lower-grid"><div className="panel activity-panel"><div className="panel-heading"><div><p className="section-kicker">AUDIT TRAIL</p><h2>Latest activity</h2></div><span className="tiny-count">{selectedEvents.length} events</span></div><div className="event-list">{selectedEvents.length === 0 ? <div className="empty-state"><div className="empty-icon"><Icon name="pulse" /></div><strong>No activity yet</strong><span>Run the team to watch decisions and MCP calls appear here.</span></div> : selectedEvents.slice(-8).reverse().map((event, index) => <div className="event-row" key={`${event.run_id}-${event.step}-${index}`}><div className={`event-dot ${event.event.includes('mcp') ? 'tool' : event.event.includes('delegation') ? 'delegate' : 'agent'}`}><Icon name={event.event.includes('mcp') ? 'spark' : event.event.includes('delegation') ? 'arrow' : 'pulse'} size={13} /></div><div className="event-copy"><div><strong>{event.agent.replaceAll('_', ' ')}</strong><span>{event.event.replaceAll('_', ' ')}</span></div><p>{event.agent_said || event.action}</p>{event.tool && <span className="event-tool">tool · {event.tool}</span>}</div><time>{timeLabel(event.timestamp)}</time></div>)}</div></div>
          <div className="panel approval-panel"><div className="panel-heading"><div><p className="section-kicker">HUMAN GATE</p><h2>Approvals</h2></div><div className="lock-mark">⌁</div></div><p className="panel-subtitle">Agents can prepare a payment. Only you can release cash.</p>{approvalTarget ? <div className="approval-form"><div className="approval-target"><div className="approval-target-icon"><Icon name="wallet" size={17} /></div><div><strong>{approvalTarget.label}</strong><span>{approvalTarget.kind === 'purchase' ? 'Purchase request · enter amount' : 'Prepared from the working database'}</span></div></div>{approvalTarget.kind === 'purchase' && <label>Amount<input type="number" min="0.01" step="0.01" value={purchaseAmount} onChange={(event) => setPurchaseAmount(event.target.value)} placeholder="0.00" /></label>}<label>Your name<input value={approver} onChange={(event) => setApprover(event.target.value)} placeholder="Human approver" /></label><button className="approve-button" disabled={approving || !approver.trim() || (approvalTarget.kind === 'purchase' && (!purchaseAmount || Number(purchaseAmount) <= 0))} onClick={() => void approveSelectedPayment()}>{approving ? <><span className="spinner dark" /> Approving…</> : <><Icon name="check" size={15} /> Approve & release cash</>}</button><small className="approval-note">This action updates <code>payments</code> and <code>cash_accounts</code>.</small></div> : <div className="empty-approval"><div className="empty-icon"><Icon name="wallet" /></div><strong>No payment request attached</strong><span>Choose a ticket with a prepared obligation to review it here.</span></div>}</div></section>
        <footer className="footer"><span>Campus Customs desk</span><span>Human-led · agent-assisted · MCP-grounded</span><span>v1.0</span></footer>
      </main>
    </div>
  )
}

export default App
