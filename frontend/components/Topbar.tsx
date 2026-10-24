import { FileSearch, LogOut as MoveOut, FilePlus2 } from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

type Page = "new" | "review" | "moveout";

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;
const CRUMB: Record<Page, string> = { new: "New review", review: "Review report", moveout: "Move-out" };

/** Dhara mark: a section sign, the unit every finding is anchored to. */
function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <rect width="22" height="22" rx="5" fill="currentColor" />
      <text x="11" y="16" textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--paper)" fontFamily="var(--sans)">
        §
      </text>
    </svg>
  );
}

export function Topbar({ current }: { current: Page }) {
  const link = (page: Page, href: string, label: string, icon: React.ReactNode) => (
    <Link className={`nav-link ${current === page ? "is-current" : ""}`} href={href} aria-current={current === page ? "page" : undefined}>
      {icon}
      <span className="nav-label">{label}</span>
    </Link>
  );
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link className="brand" href="/" aria-label="Dhara AI, home">
          <Logo />
          <span>Dhara AI</span>
          <span className="brand-sep" aria-hidden="true">
            /
          </span>
          <span className="brand-crumb">{CRUMB[current]}</span>
        </Link>
        <nav className="topnav" aria-label="Main">
          {link("new", "/", "New review", <FilePlus2 {...ICON} />)}
          {link("review", "/review/blr_flat", "Sample report", <FileSearch {...ICON} />)}
          {link("moveout", "/moveout/moveout", "Move-out", <MoveOut {...ICON} />)}
          <span className="nav-divider" aria-hidden="true" />
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
