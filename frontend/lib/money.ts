// Minor units -> display string. The API only ever sends minor units (Doc §7:
// money in paise, never float); dividing by 100 happens here and nowhere
// else, so a rounding bug has exactly one place to live (R-008 §"Money
// formatting").
export function formatMoney(minor: number, currency = "INR", locale = "en-IN"): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(minor / 100);
}
