"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";
const KEY = "dhara-theme";
const EVENT = "dhara-theme-change";

const DARK_QUERY = "(prefers-color-scheme: dark)";

/** The theme on screen: the saved choice (data-theme on <html>) or, with nothing saved, the OS setting. */
function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

function subscribe(onChange: () => void): () => void {
  const mq = window.matchMedia(DARK_QUERY);
  mq.addEventListener("change", onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    mq.removeEventListener("change", onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

function commit(next: Theme): void {
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    // storage blocked: the choice lasts for this page
  }
  window.dispatchEvent(new Event(EVENT));
}

type ViewTransitionDocument = Document & { startViewTransition?: (update: () => void) => unknown };

/**
 * Light/dark switch. With nothing saved the page follows the OS; a click saves the opposite of what is shown.
 * The switch is a short crossfade of the whole page (View Transitions API, opacity only, so text stays crisp);
 * browsers without it get a colour fade, and prefers-reduced-motion switches instantly.
 */
export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, currentTheme, () => null);

  const toggle = () => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    const root = document.documentElement;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return commit(next);

    const doc = document as ViewTransitionDocument;
    if (doc.startViewTransition) {
      doc.startViewTransition(() => commit(next));
      return;
    }
    root.classList.add("theme-fade");
    commit(next);
    window.setTimeout(() => root.classList.remove("theme-fade"), 300);
  };

  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  return (
    <button type="button" className="icon-btn" onClick={toggle} aria-label={label} title={label}>
      {theme === "dark" ? <Sun size={16} strokeWidth={1.75} aria-hidden /> : <Moon size={16} strokeWidth={1.75} aria-hidden />}
    </button>
  );
}
