// Ledgerly brand: an abstract ledger "L" with a small gold coin, on a deep-green rounded square.
// Purely presentational, no logic. The same shapes live in public/favicon.svg.
export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="8" fill="#0f5c46" />
      <rect x="9" y="7" width="4.5" height="18" rx="2" fill="#eaf5f0" />
      <rect x="9" y="20.5" width="15" height="4.5" rx="2" fill="#eaf5f0" />
      <circle cx="21.5" cy="11.5" r="3.2" fill="#d4af5a" />
    </svg>
  );
}

export function Brand({ stacked = false }: { stacked?: boolean }) {
  return (
    <div className={stacked ? "brand brand-stacked" : "brand"}>
      <LogoMark size={stacked ? 44 : 30} />
      <h1 className="brand-name">Ledgerly</h1>
    </div>
  );
}
