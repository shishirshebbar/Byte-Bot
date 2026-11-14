import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownLeft, Check, Clock3, Search, SearchCheck, Wallet, X } from 'lucide-react';
import type { Transaction } from './api';
import { money } from './transaction-ui';
import './teammate.css';

const FILTERS = [['all', 'All'], ['successful', 'Received'], ['pending', 'Pending'], ['failed', 'Failed']] as const;
const IST = 'Asia/Kolkata';
const dayKey = (value: string | Date) => new Intl.DateTimeFormat('en-CA', { timeZone: IST }).format(new Date(value));
const time = (value: string) => new Intl.DateTimeFormat('en-IN', { timeStyle: 'short', timeZone: IST }).format(new Date(value));

function dayLabel(key: string) {
  const today = dayKey(new Date());
  const yesterday = dayKey(new Date(Date.now() - 86_400_000));
  if (key === today) return 'Today';
  if (key === yesterday) return 'Yesterday';
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(key));
}

function Badge({ status }: { status: Transaction['status'] }) {
  const Icon = status === 'successful' ? Check : status === 'pending' ? Clock3 : X;
  return <span className={`tx-badge ${status}`} aria-hidden="true"><Icon size={9} strokeWidth={3.5} /></span>;
}

export function PhoneHistory({ transactions }: { transactions: Transaction[] }) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>('all');
  const [query, setQuery] = useState('');
  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const visible = transactions.filter(t => (filter === 'all' || t.status === filter) &&
      (!needle || `${t.sender_name} ${t.sender_vpa} ${t.reference}`.toLowerCase().includes(needle)));
    const map = new Map<string, Transaction[]>();
    for (const t of visible) map.set(dayKey(t.occurred_at), [...(map.get(dayKey(t.occurred_at)) || []), t]);
    return [...map.entries()];
  }, [transactions, filter, query]);
  const received = transactions.filter(t => t.status === 'successful').reduce((sum, t) => sum + t.amount_paise, 0);
  return <div className="phone-history">
    <h1>Balance &amp; History</h1>

    <Link className="push-card claim-card" to="/check-payment" aria-label="Someone says they paid you? Check whether the money arrived">
      <span className="push-icon"><SearchCheck size={18} aria-hidden="true" /></span>
      <span><strong>Someone says they paid you?</strong><small>Check whether the money really arrived before sending anything back.</small></span>
    </Link>
    <div className="summary-chips">
      <span><Wallet size={16} aria-hidden="true" />Received {money({ ...transactions[0], amount_paise: received })}</span>
      <span>{transactions.length} payments</span>
    </div>
    <label className="tx-search"><Search size={15} aria-hidden="true" /><input type="search" aria-label="Search transactions" placeholder="Search name, UPI ID or reference" value={query} onChange={e => setQuery(e.target.value)} /></label>
    <div className="filter-chips" role="group" aria-label="Filter by status">
      {FILTERS.map(([value, label]) => <button key={value} type="button" className={`chip ${filter === value ? 'selected' : ''}`} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}
    </div>
    {groups.length === 0 ? <p className="notice">No matching payments.</p> : groups.map(([key, items]) => <section key={key} className="tx-group" aria-label={dayLabel(key)}>
      <h2>{dayLabel(key)}</h2>
      <ul>{items.map(t => <li key={t.id}><Link to={`/transactions/${t.id}`} className="tx-row">
        <span className="tx-time">{time(t.occurred_at)}</span>
        <span className={`tx-icon ${t.status}`}><ArrowDownLeft size={18} aria-hidden="true" /><Badge status={t.status} /></span>
        <span className="tx-main"><strong>{t.sender_name}</strong>
          <small>№ {t.reference}</small></span>
        <span className={`tx-amount amt-${t.status}`}>{t.status === 'failed' ? '' : '+'}{money(t)}<small>{t.status === 'successful' ? 'Received' : t.status === 'pending' ? 'Pending' : 'Failed'}</small></span>
      </Link></li>)}</ul>
    </section>)}
    <p className="footnote">Synthetic demo payments. No connection to a bank or UPI account.</p>
  </div>;
}
