import type { ReactNode } from 'react'

export function Card({ title, actions, children, flush }: {
  title?: ReactNode
  actions?: ReactNode
  children: ReactNode
  flush?: boolean
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card__head">
          {title && <h2>{title}</h2>}
          <div className="spacer" />
          {actions}
        </header>
      )}
      <div className={flush ? 'card__body card__body--flush' : 'card__body'}>{children}</div>
    </section>
  )
}

export function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}

export function Tile({ label, value, unit, sub }: {
  label: string
  value: ReactNode
  unit?: string
  sub?: ReactNode
}) {
  return (
    <div className="tile">
      <div className="tile__label">{label}</div>
      <div className="tile__value">
        {value}
        {unit && <span className="tile__unit">{unit}</span>}
      </div>
      {sub && <div className="tile__sub">{sub}</div>}
    </div>
  )
}

export function Field({ label, required, hint, error, children }: {
  label: string
  required?: boolean
  hint?: ReactNode
  error?: string
  children: ReactNode
}) {
  return (
    <div className="field">
      <label>
        {label}
        {required && <span className="req">*</span>}
      </label>
      {children}
      {error ? <span className="field__err">{error}</span>
        : hint ? <span className="field__hint">{hint}</span> : null}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

export function ProgressBar({ pct }: { pct: number }) {
  const v = Math.max(0, Math.min(100, pct))
  return (
    <div className="bar" title={`${v}%`}>
      <div className={`bar__fill${v >= 100 ? ' bar__fill--done' : ''}`} style={{ width: `${v}%` }} />
    </div>
  )
}

export function Alert({ tone = 'info', title, items, children }: {
  tone?: 'info' | 'warn' | 'error'
  title?: ReactNode
  items?: string[]
  children?: ReactNode
}) {
  return (
    <div className={`alert alert--${tone}`}>
      {title && <strong>{title}</strong>}
      {children}
      {items && items.length > 0 && (
        <ul>{items.map((m, i) => <li key={i}>{m}</li>)}</ul>
      )}
    </div>
  )
}

export function Modal({ title, wide, onClose, footer, children }: {
  title: ReactNode
  wide?: boolean
  onClose: () => void
  footer?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="modal-back" onClick={onClose}>
      <div className={wide ? 'modal modal--wide' : 'modal'} onClick={(e) => e.stopPropagation()}>
        <header className="modal__head">
          <h3>{title}</h3>
          <div style={{ flex: 1 }} />
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose}>✕</button>
        </header>
        <div className="modal__body">{children}</div>
        {footer && <footer className="modal__foot">{footer}</footer>}
      </div>
    </div>
  )
}

export function Toast({ message }: { message: string }) {
  return <div className="toast">{message}</div>
}
