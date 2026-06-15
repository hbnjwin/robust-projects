export function formatPowerMw(watts: number | null | undefined): string {
  if (watts == null || Number.isNaN(watts)) return '0.00 MW'
  const mw = watts / 1000000
  if (Math.abs(mw) < 0.005) return '0.00 MW'
  return `${mw.toFixed(2)} MW`
}

export function kWToMW(kw: number): number {
  return kw / 1000
}
