import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownLeft, ArrowRight, Bot, Building2, Clock3, ScanLine, UserRound, Users, Wallet, X } from 'lucide-react';
import type { Transaction } from './api';
import { money, Status } from './transaction-ui';

export function PhoneHome({ transactions }: { transactions: Transaction[] }) {
  const [notice, setNotice] = useState('');
  return <div className="paytm-home">
    <div className="home-greeting"><span className="home-profile"><UserRound size={22} /></span><div><small>Welcome back</small><h1>Let's make it simple.</h1></div></div>
    <section className="home-payments" aria-label="UPI payments">
      <h2>UPI payments</h2>
      <div className="home-shortcuts">
        {([{ icon: ScanLine, label: 'Scan & Pay' }, { icon: Users, label: 'To mobile' }, { icon: Building2, label: 'To bank' }]).map(({ icon: ShortcutIcon, label }) => {
          return <button key={label} type="button" onClick={() => setNotice(`${label} is a preview in this prototype. No money can be moved.`)}><ShortcutIcon size={25} aria-hidden="true" /><span>{label}</span></button>;
        })}
        <Link to="/history"><Wallet size={25} aria-hidden="true" /><span>Balance &amp; History</span></Link>
      </div>
      <p className="home-upi-note">Fast. Simple. Secure.</p>
    </section>
    {notice && <div className="home-notice" role="status"><p>{notice}</p><button className="icon-button" aria-label="Dismiss prototype notice" onClick={() => setNotice('')}><X size={18} /></button></div>}
    <Link className="home-bot" to="/check-payment"><span className="home-bot-icon"><Bot size={25} aria-hidden="true" /></span><div><small>YOUR PAYMENT SAFETY ASSISTANT</small><strong>Something feels wrong?</strong><p>Check a payment with Byte Bot.</p></div><ArrowRight size={19} aria-hidden="true" /></Link>
    <section className="home-recent" aria-label="Recent payments"><div className="home-section-title"><h2>Recent payments</h2><Link to="/history">View all</Link></div>
      {transactions.length === 0 ? <p>No payments yet.</p> : <ul>{transactions.slice(0, 3).map(t => <li key={t.id}><Link to={`/transactions/${t.id}`}><span className="recent-icon"><ArrowDownLeft size={20} aria-hidden="true" /></span><span className="recent-person"><strong>{t.sender_name}</strong><Status value={t.status} /></span><b>{money(t)}</b></Link></li>)}</ul>}
    </section>
    <Link className="home-help" to="/incidents"><Clock3 size={18} aria-hidden="true" /> Your Byte Bot cases <ArrowRight size={16} aria-hidden="true" /></Link>
    <p className="home-demo-note">Paytm-style prototype · Synthetic payments</p>
  </div>;
}
