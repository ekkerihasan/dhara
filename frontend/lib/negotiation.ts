// Mirrors backend.agent.landlord models. This feature always uses a live model.
export interface NegotiationStatement {
  text: string;
  section_id: string | null;
  verdict: "cited" | "unverified" | "blocked";
  reason: string;
}

export interface Negotiation {
  id: string;
  status: "running" | "ready" | "accepted" | "exhausted" | "failed";
  simulated: boolean;
  delivery_status: "not_sent";
  rounds_remaining: number;
  turns: { round: number; tenant_message: string; decision: "accept" | "counter" | "reject";
    reply: string; statements: NegotiationStatement[]; source: "model"; simulated: boolean }[];
  trace: { type: "plan" | "question" | "tool_call" | "verifier" | "draft" | "approval";
    label: string; data: Record<string, unknown> }[];
  not_a_lawyer: boolean;
  notice: string;
  error: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function negotiationRequest(path: string, body?: unknown, signal?: AbortSignal): Promise<Negotiation> {
  const response = await fetch(`${API_URL}/api/negotiations${path}`, {
    ...(body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
    signal,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `Negotiation request failed (${response.status}).`);
  }
  return response.json() as Promise<Negotiation>;
}
