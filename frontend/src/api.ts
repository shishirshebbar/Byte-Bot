export type Transaction = {
  id: string; direction: 'incoming'; amount_paise: number; currency: 'INR';
  sender_name: string; sender_vpa: string; receiver_vpa: string;
  occurred_at: string; status: 'successful' | 'pending' | 'failed';
  reference: string; source: 'mock';
};
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, credentials: 'same-origin' });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.error?.message || 'The request could not be completed. Please try again.');
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export function get<T>(path: string, signal: AbortSignal): Promise<T> { return request<T>(path, { signal }); }
export function json<T>(path: string, method: string, body: unknown): Promise<T> {
  return request<T>(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}
