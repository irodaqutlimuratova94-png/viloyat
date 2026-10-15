export const money = (v: number) => v.toLocaleString("ru-RU").replace(/\u00a0/g, " ") + " so‘m";
export const dt = (iso: string) =>
  new Intl.DateTimeFormat("uz-UZ", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Tashkent" }).format(new Date(iso));
export const placeName = (region: string, city: string | null, names: Record<string, string>) => `${names[region] ?? region}${city ? `, ${city}` : ""}`;
