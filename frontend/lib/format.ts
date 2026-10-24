import type { LocalBody, RunStatus } from "./types";

/** Indian digit grouping: 250000 -> "Rs 2,50,000". */
export function inr(amount: number): string {
  return `Rs ${amount.toLocaleString("en-IN")}`;
}

export function time(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });
}

export function date(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
}

export const LOCAL_BODY_LABEL: Record<LocalBody, string> = {
  municipal_corporation: "Municipal corporation (Part A)",
  city_municipal_council: "City municipal council (Part B)",
  other: "Other / not sure",
};

export const STATUS_LABEL: Record<RunStatus, string> = {
  running: "Running",
  needs_input: "Needs your answer",
  awaiting_approval: "Awaiting your approval",
  approved: "Approved, follow-up scheduled",
  failed: "Failed",
};
