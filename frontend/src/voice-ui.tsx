import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Volume2 } from 'lucide-react';
import { json, request } from './api';
import type { Evidence } from './investigation-types';

export const LANGUAGES: [string, string][] = [
  ['hi-IN', 'हिन्दी Hindi'], ['en-IN', 'English'], ['ta-IN', 'தமிழ் Tamil'], ['te-IN', 'తెలుగు Telugu'],
  ['kn-IN', 'ಕನ್ನಡ Kannada'], ['bn-IN', 'বাংলা Bengali'], ['mr-IN', 'मराठी Marathi'], ['gu-IN', 'ગુજરાતી Gujarati'],
  ['ml-IN', 'മലയാളം Malayalam'], ['pa-IN', 'ਪੰਜਾਬੀ Punjabi'], ['od-IN', 'ଓଡ଼ିଆ Odia'],
];
const MAX_SECONDS = 25;

/** Record or upload a short voice note. Audio stays in memory and is transcribed by Sarvam. */
export function VoiceNote({ base, revision, disabled, onDone }: {
  base: string; revision: number; disabled: boolean; onDone: (result: { evidence: Evidence; input_revision: number }) => void;
}) {
  const [language, setLanguage] = useState('unknown');
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => () => { clearInterval(timer.current); recorder.current?.stream.getTracks().forEach(t => t.stop()); }, []);

  async function send(blob: Blob) {
    setBusy(true); setError('');
    try {
      const form = new FormData();
      form.append('file', blob, 'voice-note');
      form.append('expected_revision', String(revision));
      onDone(await request(`${base}/voice?language=${language}`, { method: 'POST', body: form }));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function start() {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const media = new MediaRecorder(stream);
      media.ondataavailable = event => chunks.push(event.data);
      media.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        clearInterval(timer.current);
        setRecording(false);
        void send(new Blob(chunks, { type: media.mimeType.split(';')[0] || 'audio/webm' }));
      };
      recorder.current = media;
      media.start();
      setRecording(true); setSeconds(0);
      timer.current = setInterval(() => setSeconds(value => {
        if (value + 1 >= MAX_SECONDS) media.state === 'recording' && media.stop();
        return value + 1;
      }), 1000);
    } catch { setError('Microphone access is unavailable. Upload an audio file or type a call summary instead.'); }
  }
  return <div className="voice-note">
    <label className="field">Voice note language<select aria-label="Voice note language" value={language} disabled={disabled || busy || recording} onChange={e => setLanguage(e.target.value)}>
      <option value="unknown">Detect automatically</option>{LANGUAGES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
    </select></label>
    <div className="actions">
      {!recording ? <button type="button" disabled={disabled || busy} onClick={() => void start()}><Mic size={16} aria-hidden="true" /> {busy ? 'Transcribing with Sarvam…' : 'Record voice note'}</button>
        : <button type="button" className="recording" onClick={() => recorder.current?.stop()}><Square size={14} aria-hidden="true" /> Stop · {MAX_SECONDS - seconds}s left</button>}
      <label className="secondary file-button">Upload audio<input type="file" accept="audio/*" disabled={disabled || busy || recording}
        onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void send(file); }} /></label>
    </div>
    <p className="field-help">Speak in Hindi, Hinglish, or another Indian language (up to {MAX_SECONDS} seconds). Sarvam AI transcribes and translates it; the audio is not stored. Review the transcript before analysis.</p>
    {error && <p role="alert" className="error-box">{error}</p>}
  </div>;
}

/** Play Byte Bot's own guidance in the customer's language via Sarvam text-to-speech. */
export function ListenGuidance({ caseId }: { caseId: string }) {
  const [language, setLanguage] = useState('hi-IN');
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  async function listen() {
    setBusy(true); setError('');
    try {
      const spoken = await json<{ text: string; audio_base64: string; media_type: string }>(`/investigations/${caseId}/speak`, 'POST', { language });
      setText(spoken.text);
      await new Audio(`data:${spoken.media_type};base64,${spoken.audio_base64}`).play();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="listen">
    <select aria-label="Guidance language" value={language} onChange={e => setLanguage(e.target.value)}>
      {LANGUAGES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
    </select>
    <button type="button" className="secondary" disabled={busy} onClick={() => void listen()}><Volume2 size={15} aria-hidden="true" /> {busy ? 'Preparing audio…' : 'Listen'}</button>
    {text && <p className="listen-text" lang={language.split('-')[0]}>{text}</p>}
    {error && <p role="alert" className="error-box">{error}</p>}
  </div>;
}
