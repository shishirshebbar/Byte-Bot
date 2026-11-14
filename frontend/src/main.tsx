import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider, Outlet, Link, useLocation, useOutletContext, useParams, type RouteObject } from 'react-router-dom';
import { ArrowDownLeft, ArrowLeft, ArrowUpRight, ShieldCheck } from 'lucide-react';
import '@fontsource-variable/manrope';
import './tokens.css';
import './styles.css';
import { ApiError, get, type Transaction } from './api';
import { date, money, Status } from './transaction-ui';
import { AskByteBot, InvestigationPage } from './investigation';
import { ResultsPage } from './results';
import { IncidentsPage } from './incidents';
import { ReportPage } from './report';
import { DemoControls } from './demo';
import { Presentation } from './presentation';
import { useScreenPath } from './screen-path';
import { PhoneHistory } from './phone-history';
import { ConsolePage } from './console';
import { MetricsPage } from './metrics';
import { ClaimCheckPage } from './story-ui';

function useData<T>(path: string, refresh = 0) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(undefined); setError(undefined);
    get<T>(path, controller.signal).then(value => { if (!controller.signal.aborted) setData(value); }).catch(err => {
      if (!controller.signal.aborted) setError(err);
    });
    return () => controller.abort();
  }, [path, attempt, refresh]);
  return { data, error, retry: () => setAttempt(v => v + 1) };
}
function Notice({ error, retry }: { error?: ApiError; retry: () => void }) {
  if (!error) return <p role="status" className="notice">Loading transaction data…</p>;
  return <div role="alert" className="notice"><h2>{error.status === 404 ? 'Transaction unavailable' : 'Could not load this page'}</h2><p>{error.message}</p><button onClick={retry}>Try again</button></div>;
}
function WorkspaceHistory() {
  const [refresh, setRefresh] = useState(0);
  const transactions = useTransactions(refresh);
  return <History transactions={transactions} controls={<DemoControls ready={!!transactions.data} onReset={() => setRefresh(value => value + 1)} />} />;
}

function useTransactions(refresh = 0) {
  return useData<{ transactions: Transaction[] }>('/transactions', refresh);
}

function History({ transactions: { data, error, retry }, controls }: {
  transactions: ReturnType<typeof useTransactions>;
  controls?: React.ReactNode;
}) {
  const screen = useScreenPath();
  return <><div className="eyebrow">YOUR ACTIVITY</div><h1>Transaction history</h1><p className="intro">A clear view of your incoming payments.</p>
    {controls}
    <section className="panel" aria-label="Incoming transactions"><div className="panel-heading"><h2>Incoming payments</h2><span>INR · India</span></div>
      {!data ? <Notice error={error} retry={retry} /> : data.transactions.length === 0 ? <p className="notice">No incoming transactions yet.</p> : <ul className="transactions">{data.transactions.map(t => <li key={t.id}><Link to={screen(`/transactions/${t.id}`)} className="transaction"><span className="avatar"><ArrowDownLeft aria-hidden="true" /></span><span className="sender"><strong>{t.sender_name}</strong><span>{date(t.occurred_at)} IST</span></span><span className="amount"><strong>{money(t)}</strong><Status value={t.status} /></span><ArrowUpRight className="open-icon" aria-hidden="true" /></Link></li>)}</ul>}
    </section><p className="footnote">Source: synthetic transaction records. These are demo payments, with no connection to a bank or UPI account.</p></>;
}
function Detail() {
  const { id } = useParams();
  const screen = useScreenPath();
  const presentation = useLocation().pathname.startsWith('/transactions/');
  const { data: t, error, retry } = useData<Transaction>(`/transactions/${encodeURIComponent(id || '')}`);
  return <><Link className="back" to={screen('/')}><ArrowLeft size={18} aria-hidden="true" /> All transactions</Link><h1>Transaction details</h1>
    {!t ? <Notice error={error} retry={retry} /> : <section className="panel detail"><div className="payment-summary"><span className="avatar"><ArrowDownLeft aria-hidden="true" /></span><p>{t.status === 'successful' ? 'Received from' : 'Incoming payment from'} {t.sender_name}</p><div className="hero-amount">{money(t)}</div><Status value={t.status} /><p className="status-explanation">{t.status === 'successful' ? 'This demo payment completed successfully.' : t.status === 'pending' ? 'This payment is pending. Funds are not confirmed as received.' : 'This payment failed. Funds were not received.'}</p>{presentation && <AskByteBot transactionId={t.id} />}</div><dl>{[
      ['Sender', t.sender_name], ['Sender UPI ID', t.sender_vpa], ['Recipient UPI ID', t.receiver_vpa], ['Date & time', `${date(t.occurred_at)} IST`], ['Transaction reference', t.reference], ['Direction', 'Incoming'], ['Currency', t.currency], ['Source', 'Synthetic demo record (mock)'],
    ].map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl></section>}
    {t && !presentation && <AskByteBot transactionId={t.id} />}<p className="footnote">Demo transaction facts only. No money can be sent, returned, or reversed here.</p></>;
}
function WorkspaceLayout() {
  return <><header><Link to="/workspace" className="brand"><span className="brand-icon"><ShieldCheck aria-hidden="true" /></span>Byte Bot</Link><nav aria-label="Main navigation"><Link to="/workspace/incidents">My Incidents</Link></nav><span className="demo-badge">SYNTHETIC DEMO</span></header><main><Outlet /></main><footer>Byte Bot · Transaction review workspace</footer></>;
}

function PresentationLayout() {
  const { pathname } = useLocation();
  const [refresh, setRefresh] = useState(0);
  const transactions = useTransactions(refresh);
  return <Presentation ready={!!transactions.data} onReset={() => setRefresh(value => value + 1)} sessionRetry={transactions.error ? transactions.retry : undefined}>
    {pathname === '/' || transactions.data ? <Outlet context={transactions} /> :
      <Notice error={transactions.error} retry={transactions.retry} />}
  </Presentation>;
}

function PresentationHistory() {
  const { data, error, retry } = useOutletContext<ReturnType<typeof useTransactions>>();
  return data ? <PhoneHistory transactions={data.transactions} /> : <><h1>Transaction history</h1><Notice error={error} retry={retry} /></>;
}

function MissingPage() {
  const screen = useScreenPath();
  return <><h1>Page not found</h1><Link to={screen('/')}>Return to transactions</Link></>;
}

const screens: RouteObject[] = [
  { path: 'transactions/:id', element: <Detail /> },
  { path: 'investigations/:id', element: <InvestigationPage /> },
  { path: 'investigations/:id/results', element: <ResultsPage /> },
  { path: 'investigations/:id/report', element: <ReportPage /> },
  { path: 'incidents', element: <IncidentsPage /> },
  { path: 'check-payment', element: <ClaimCheckPage /> },
  { path: '*', element: <MissingPage /> },
];
const router = createBrowserRouter([
  { path: '/', element: <PresentationLayout />, children: [{ index: true, element: <PresentationHistory /> }, ...screens] },
  { path: '/metrics', element: <MetricsPage /> },
  { path: '/console', element: <ConsolePage /> },
  { path: '/console/cases/:id', element: <ConsolePage /> },
  { path: '/console/integrations', element: <ConsolePage view="integrations" /> },
  { path: '/workspace', element: <WorkspaceLayout />, children: [{ index: true, element: <WorkspaceHistory /> }, ...screens] },
]);
createRoot(document.getElementById('root')!).render(<React.StrictMode><RouterProvider router={router} /></React.StrictMode>);
