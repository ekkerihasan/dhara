import { CircleCheck, CircleHelp, Ban } from "lucide-react";
import type { Verdict } from "@/lib/types";

const STYLE: Record<Verdict, { className: string; label: string; Icon: typeof Ban }> = {
  cited: { className: "badge-green", label: "Cited", Icon: CircleCheck },
  unverified: { className: "badge-amber", label: "Unverified", Icon: CircleHelp },
  blocked: { className: "badge-red", label: "Blocked", Icon: Ban },
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { className, label, Icon } = STYLE[verdict];
  return (
    <span className={`badge ${className}`}>
      <Icon size={12} strokeWidth={2} aria-hidden />
      {label}
    </span>
  );
}
