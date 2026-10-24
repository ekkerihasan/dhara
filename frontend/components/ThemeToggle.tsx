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

const GROW_MS = 420;
const FADE_MS = 180;

/**
 * Light/dark switch. With nothing saved the page follows the OS; a click saves the opposite of what is shown.
 * A circle in the new theme's background grows from the button to the farthest corner, the theme switches
 * underneath it, then the circle fades away. Only transform and opacity animate, so the GPU does the work and
 * text never repaints mid-motion. prefers-reduced-motion switches instantly.
 */
export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, currentTheme, () => null);
  const button = useRef<HTMLButtonElement>(null);
  const busy = useRef(false);

  const toggle = () => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return commit(next);
    if (busy.current) return;
    busy.current = true;

    // Centre on the button; the radius reaches the farthest corner of the viewport.
    const rect = button.current?.getBoundingClientRect();
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth - 40;
    const y = rect ? rect.top + rect.height / 2 : 32;
    const radius = Math.ceil(Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y)));

    const wipe = document.createElement("div");
    wipe.className = "theme-wipe";
    wipe.dataset.to = next;
    Object.assign(wipe.style, { left: `${x - radius}px`, top: `${y - radius}px`, width: `${radius * 2}px`, height: `${radius * 2}px` });
    document.body.appendChild(wipe);

    wipe.animate([{ transform: "scale(0)" }, { transform: "scale(1)" }], { duration: GROW_MS, easing: "cubic-bezier(0.4, 0, 0.2, 1)", fill: "forwards" });
    // Timers, not animation events, drive the steps, so a hidden tab can never leave the circle on screen.
    window.setTimeout(() => {
      commit(next); // hidden under the circle
      wipe.animate([{ opacity: 1 }, { opacity: 0 }], { duration: FADE_MS, easing: "ease-out", fill: "forwards" });
    }, GROW_MS);
    window.setTimeout(() => {
      wipe.remove();
      busy.current = false;
    }, GROW_MS + FADE_MS + 20);
  };

  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  return (
    <button ref={button} type="button" className="icon-btn" onClick={toggle} aria-label={label} title={label}>
      {theme === "dark" ? <Sun size={16} strokeWidth={1.75} aria-hidden /> : <Moon size={16} strokeWidth={1.75} aria-hidden />}
    </button>
  );
}
