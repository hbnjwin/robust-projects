// ---------------------------------------------------------------------------
// Cross-browser date parsing utilities
// ---------------------------------------------------------------------------

/**
 * Parse an ISO-ish date string into a Date object in a way that works
 * reliably across browsers — including Safari.
 *
 * BUG (fixed): Safari's `Date` constructor rejects ISO 8601 strings
 * that use a space separator instead of "T" (e.g. "2024-01-15 10:30:00").
 * It also chokes on strings without an explicit timezone offset, parsing
 * them inconsistently or returning Invalid Date.
 *
 * FIX:
 *  1. Replace space separators with "T".
 *  2. Append "Z" (UTC) if no timezone indicator is present, so the
 *     behaviour is consistent across engines.
 *  3. Validate the result and throw a clear error on failure.
 */
export function parseDateSafe(value: string): Date {
  // Normalise whitespace separator → "T"
  let normalised = value.trim().replace(' ', 'T')

  // Append UTC indicator when no timezone info is present.
  // Matches trailing Z, +HH:MM, -HH:MM, +HHMM, -HHMM
  if (!/[Zz]$/.test(normalised) && !/[+-]\d{2}:?\d{2}$/.test(normalised)) {
    normalised += 'Z'
  }

  const date = new Date(normalised)

  if (Number.isNaN(date.getTime())) {
    throw new RangeError(`Cannot parse date string: "${value}"`)
  }

  return date
}
