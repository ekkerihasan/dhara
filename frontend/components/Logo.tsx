/** Dhara mark: a "D" drawn as a page holding two clauses, the lower one flagged in the accent colour. */
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" fillRule="evenodd" d="M3 3h9a9 9 0 0 1 0 18H3zM5.5 5.5v13H12a6.5 6.5 0 0 0 0-13z" />
      <rect x="8.5" y="8.5" width="6" height="2" fill="currentColor" />
      <rect x="8.5" y="13.5" width="4" height="2" fill="var(--accent)" />
    </svg>
  );
}
