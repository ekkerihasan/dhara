"use client";

import { Mic, Square } from "lucide-react";
import { useRef, useState } from "react";
import { USE_STUBS, voiceFacts } from "@/lib/api";
import type { Facts, Language } from "@/lib/types";

const MAX_SECONDS = 20;

type State = { kind: "idle" } | { kind: "recording"; seconds: number } | { kind: "sending" } | { kind: "done"; transcript: string; filled: number } | { kind: "error"; message: string };

/** "Speak the terms": records a short description, and the backend turns it into form fields the tenant then checks. */
export function VoiceFacts({ language, onFacts }: { language: Language; onFacts: (facts: Partial<Facts>) => void }) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | null>(null);

  const stop = () => {
    if (timer.current) window.clearInterval(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  };

  const start = async () => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setState({ kind: "error", message: "Microphone access was blocked. Allow it in the browser, or type the facts." });
      return;
    }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(stream);
    recorder.current = rec;
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      setState({ kind: "sending" });
      try {
        const result = await voiceFacts(new Blob(chunks, { type: rec.mimeType || "audio/webm" }), language);
        onFacts(result.facts);
        setState({ kind: "done", transcript: result.transcript, filled: Object.keys(result.facts).length });
      } catch (err) {
        setState({ kind: "error", message: err instanceof Error ? err.message : "Could not read the recording." });
      }
    };
    rec.start();
    setState({ kind: "recording", seconds: 0 });
    const started = Date.now();
    timer.current = window.setInterval(() => {
      const seconds = Math.floor((Date.now() - started) / 1000);
      if (seconds >= MAX_SECONDS) stop();
      else setState({ kind: "recording", seconds });
    }, 250);
  };

  if (USE_STUBS) {
    return (
      <p className="field-hint" style={{ marginBottom: 12 }}>
        <Mic size={13} aria-hidden style={{ verticalAlign: "-2px" }} /> Speaking the terms needs the live backend.
      </p>
    );
  }

  return (
    <div className="form-actions" style={{ marginTop: 0, marginBottom: 16 }}>
      {state.kind === "recording" ? (
        <button type="button" className="btn btn-sm" onClick={stop}>
          <Square size={13} aria-hidden /> Stop ({MAX_SECONDS - state.seconds}s left)
        </button>
      ) : (
        <button type="button" className="btn btn-sm" onClick={start} disabled={state.kind === "sending"}>
          <Mic size={14} aria-hidden /> {state.kind === "sending" ? "Reading what you said…" : "Speak the terms"}
        </button>
      )}
      <span className="field-hint" aria-live="polite">
        {state.kind === "idle" && "Say the rent, deposit, building year and city. You check the fields before submitting."}
        {state.kind === "recording" && "Listening…"}
        {state.kind === "done" && `Heard: "${state.transcript}" · ${state.filled} field${state.filled === 1 ? "" : "s"} filled. Check them below.`}
        {state.kind === "error" && state.message}
      </span>
    </div>
  );
}
