/** Safely coerce any value to a finite number, falling back to `fallback`. */
export function num(v: unknown, fallback = 0): number {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}
