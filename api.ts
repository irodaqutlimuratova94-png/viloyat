const PUBLIC = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
const BASE = typeof window === "undefined" ? process.env.API_INTERNAL_URL ?? PUBLIC : PUBLIC;

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

// Eslatma: JWT localStorage'da saqlanadi (oddiy yechim). Production uchun httpOnly cookie ko'rib chiqing.
export const tokenKey = (admin: boolean) => (admin ? "vb_admin_token" : "vb_token");
export const getToken = (admin = false) => (typeof window === "undefined" ? null : localStorage.getItem(tokenKey(admin)));
export const setToken = (t: string | null, admin = false) =>
  t ? localStorage.setItem(tokenKey(admin), t) : localStorage.removeItem(tokenKey(admin));

function message(data: any): string {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map((x) => String(x.msg ?? "").replace("Value error, ", "")).join("; ");
  return "Xatolik yuz berdi. Qayta urinib ko‘ring.";
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: unknown; admin?: boolean; headers?: Record<string, string>; params?: Record<string, string | number | undefined | null> } = {},
): Promise<T> {
  const url = new URL(BASE + path);
  Object.entries(opts.params ?? {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && url.searchParams.set(k, String(v)));
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const tok = getToken(!!opts.admin);
  if (tok) headers.Authorization = `Bearer ${tok}`;
  let res: Response;
  try {
    res = await fetch(url, { method: opts.method ?? "GET", headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Server bilan aloqa yo‘q. Internetni tekshirib, qayta urinib ko‘ring.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, message(data));
  return data as T;
}
export const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "Xatolik yuz berdi. Qayta urinib ko‘ring.");
