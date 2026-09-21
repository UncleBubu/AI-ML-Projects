// One place for money/date display so the whole UI agrees.
const naira = new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" });
export const formatNaira = (n: number) => naira.format(n);

// Show dates in the business timezone (matches how the backend draws boundaries).
export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-NG", { timeZone: "Africa/Lagos", day: "numeric", month: "short", year: "numeric" });

export const errorMessage = (err: unknown) => (err instanceof Error ? err.message : "Something went wrong");
