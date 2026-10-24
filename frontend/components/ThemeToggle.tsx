"use client";

import { Moon, Sun } from "lucide-react";
import { useRef, useSyncExternalStore } from "react";

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

type ViewTransitionDocument = Document & { startViewTransition?: (update: () => void) => { ready: Promise<void> } };

/**
 * Light/dark switch. With nothing saved the page follows the OS; a click saves the opposite of what is shown.
 * The new theme grows as a circle from the button to the far corner (View Transitions API); browsers without
 * it get a short colour crossfade, and prefers-reduced-motion switches instantly.
 */
export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, currentTheme, () => null);
  const button = useRef<HTMLButtonElement>(null);

  const toggle = () => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    const root = document.documentElement;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return commit(next);

    const doc = document as ViewTransitionDocument;
    if (!doc.startViewTransition) {
      root.classList.add("theme-fade");
      commit(next);
      window.setTimeout(() => root.classList.remove("theme-fade"), 300);
      return;
    }

    // Start at the button's centre; the radius reaches the farthest corner of the viewport.
    const rect = button.current?.getBoundingClientRect();
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth - 40;
    const y = rect ? rect.top + rect.height / 2 : 32;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const transition = doc.startViewTransition(() => commit(next));
    transition.ready.then(() => {
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 500, easing: "cubic-bezier(0.4, 0, 0.2, 1)", pseudoElement: "::view-transition-new(root)" },
      );
    });
  };

  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  return (
    <button ref={button} type="button" className="icon-btn" onClick={toggle} aria-label={label} title={label}>
      {theme === "dark" ? <Sun size={16} strokeWidth={1.75} aria-hidden /> : <Moon size={16} strokeWidth={1.75} aria-hidden />}
    </button>
  );
}
