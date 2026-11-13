import type { Transaction } from './api';
const labels = { successful: 'Successful', pending: 'Pending', failed: 'Failed' };
export const money = (t: Transaction) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(t.amount_paise / 100);
export const date = (value: string) => new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(new Date(value));
export function Status({ value }: { value: Transaction['status'] }) { return <span className={`status ${value}`}>{labels[value]}</span>; }
export function statusExplanation(t: Transaction) {
  return t.status === 'successful' ? 'This demo payment completed successfully.' : t.status === 'pending' ? 'This payment is pending. Funds are not confirmed as received.' : 'This payment failed. Funds were not received.';
}
