"use client";
import { useCallback, useEffect, useState } from "react";
import { api, errMsg, getToken, setToken } from "@/lib/api";

type Row = Record<string, any>;
type Tab = { key: string; label: string; path: string; actions?: (r: Row, run: (fn: () => Promise<unknown>) => void) => React.ReactNode };

const btn = "btn btn-ghost !min-h-9 !px-3 !text-sm";
const A = { admin: true } as const;

const TABS: Tab[] = [
  { key: "stats", label: "Statistika", path: "/admin/stats" },
  { key: "users", label: "Foydalanuvchilar", path: "/admin/users", actions: (r, run) => <>
    <button className={btn} onClick={() => run(() => api(`/admin/users/${r.id}/block`, { method: "POST", body: { hours: 24 }, ...A }))}>24 soat blok</button>
    <button className={btn} onClick={() => run(() => api(`/admin/users/${r.id}/block`, { method: "POST", body: {}, ...A }))}>Muddatsiz blok</button>
    <button className={btn} onClick={() => run(() => api(`/admin/users/${r.id}/unblock`, { method: "POST", ...A }))}>Blokdan chiqarish</button></> },
  { key: "drivers", label: "Haydovchilar", path: "/admin/drivers", actions: (r, run) => <>
    {["verified", "rejected", "pending"].map((v) => <button key={v} className={btn} onClick={() => run(() => api(`/admin/drivers/${r.id}/verification`, { method: "POST", body: { verification: v }, ...A }))}>{v}</button>)}</> },
  { key: "trips", label: "Safarlar", path: "/admin/trips", actions: (r, run) => (
    <button className={btn} onClick={() => run(() => api(`/admin/trips/${r.id}/moderate`, { method: "POST", body: { hidden: r.moderation === "ok" }, ...A }))}>{r.moderation === "ok" ? "Yashirish" : "Ko‘rsatish"}</button>) },
  { key: "complaints", label: "Shikoyatlar", path: "/admin/complaints", actions: (r, run) => <>
    {["resolved", "rejected"].map((v) => <button key={v} className={btn} onClick={() => run(() => api(`/admin/complaints/${r.id}/resolve`, { method: "POST", body: { status: v }, ...A }))}>{v}</button>)}</> },
  { key: "subs", label: "Obunalar", path: "/admin/subscriptions" },
  { key: "pays", label: "To‘lovlar", path: "/admin/payments" },
  { key: "plans", label: "Tariflar", path: "/admin/plans", actions: (r, run) => <>
    <button className={btn} onClick={() => run(() => api(`/admin/plans/${r.id}`, { method: "PATCH", body: { is_active: !r.is_active }, ...A }))}>{r.is_active ? "O‘chirish" : "Yoqish"}</button>
    <button className={btn} onClick={() => { const v = prompt("Yangi narx (so‘m):", String(r.price_uzs)); if (v && /^\d+$/.test(v)) run(() => api(`/admin/plans/${r.id}`, { method: "PATCH", body: { price_uzs: Number(v) }, ...A })); }}>Narxni o‘zgartirish</button></> },
  { key: "audit", label: "Audit jurnali", path: "/admin/audit" },
];

const cell = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "boolean" ? (v ? "ha" : "yo‘q") : String(v));

function Settings({ run }: { run: (fn: () => Promise<unknown>) => void }) {
  const [days, setDays] = useState(""); const [plan, setPlan] = useState({ code: "", name: "", days: "", price_uzs: "" });
  const [bc, setBc] = useState({ text: "", audience: "all", region: "" });
  useEffect(() => { api<{ days: number }>("/admin/settings/trial-days", A).then((r) => setDays(String(r.days))).catch(() => {}); }, []);
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="card space-y-2"><h3 className="font-bold">Bepul sinov muddati (kun)</h3><p className="text-sm text-muted">Faqat keyin ro‘yxatdan o‘tadiganlarga ta’sir qiladi.</p>
        <input aria-label="Sinov kunlari" className="input" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))} />
        <button className="btn btn-primary w-full" onClick={() => run(() => api("/admin/settings/trial-days", { method: "PUT", body: { days: Number(days) }, ...A }))}>Saqlash</button></div>
      <div className="card space-y-2"><h3 className="font-bold">Yangi tarif</h3>
        {(["code", "name", "days", "price_uzs"] as const).map((k) => <input key={k} aria-label={k} placeholder={{ code: "kod (m1)", name: "nomi", days: "kunlar", price_uzs: "narx (so‘m)" }[k]} className="input" value={plan[k]} onChange={(e) => setPlan({ ...plan, [k]: e.target.value })} />)}
        <button className="btn btn-primary w-full" onClick={() => run(() => api("/admin/plans", { method: "POST", body: { ...plan, days: Number(plan.days), price_uzs: Number(plan.price_uzs) }, ...A }))}>Qo‘shish</button></div>
      <div className="card space-y-2"><h3 className="font-bold">Bildirishnoma</h3>
        <textarea aria-label="Matn" className="input min-h-24 py-2" value={bc.text} onChange={(e) => setBc({ ...bc, text: e.target.value })} />
        <select aria-label="Auditoriya" className="input" value={bc.audience} onChange={(e) => setBc({ ...bc, audience: e.target.value })}><option value="all">Hammaga</option><option value="drivers">Haydovchilarga</option><option value="passengers">Yo‘lovchilarga</option></select>
        <input aria-label="Hudud kodi (ixtiyoriy)" placeholder="hudud kodi (ixtiyoriy)" className="input" value={bc.region} onChange={(e) => setBc({ ...bc, region: e.target.value })} />
        <button className="btn btn-primary w-full" disabled={!bc.text} onClick={() => run(() => api("/admin/broadcast", { method: "POST", body: { text: bc.text, audience: bc.audience, region: bc.region || null }, ...A }))}>Yuborish</button></div>
    </div>
  );
}

export default function Admin() {
  const [authed, setAuthed] = useState(false); const [cred, setCred] = useState({ username: "", password: "" });
  const [tab, setTab] = useState(TABS[0]); const [data, setData] = useState<Row[] | Row | null>(null); const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  useEffect(() => setAuthed(!!getToken(true)), []);

  const load = useCallback(() => {
    setData(null);
    api<Row[] | Row>(tab.path, A).then(setData).catch((e) => { setErr(errMsg(e)); if (e?.status === 401 || e?.status === 403) { setToken(null, true); setAuthed(false); } });
  }, [tab]);
  useEffect(() => { if (authed) load(); }, [authed, load]);

  const run = async (fn: () => Promise<unknown>) => { setErr(""); setOk(""); try { await fn(); setOk("Bajarildi"); load(); } catch (e) { setErr(errMsg(e)); } };
  const login = async () => { try { const r = await api<{ access_token: string }>("/admin/login", { method: "POST", body: cred }); setToken(r.access_token, true); setAuthed(true); setErr(""); } catch (e) { setErr(errMsg(e)); } };

  if (!authed) return (
    <div className="card mx-auto max-w-sm space-y-3"><h1 className="text-2xl font-extrabold">Administrator</h1>
      <input aria-label="Login" className="input" placeholder="Login" value={cred.username} onChange={(e) => setCred({ ...cred, username: e.target.value })} />
      <input aria-label="Parol" type="password" className="input" placeholder="Parol" value={cred.password} onChange={(e) => setCred({ ...cred, password: e.target.value })} />
      {err && <p role="alert" className="text-warn">{err}</p>}<button className="btn btn-primary w-full" onClick={login}>Kirish</button></div>
  );

  const rows = Array.isArray(data) ? data : data ? [data] : [];
  const cols = rows[0] ? Object.keys(rows[0]) : [];
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h1 className="text-2xl font-extrabold">Administrator paneli</h1><button className={btn} onClick={() => { setToken(null, true); setAuthed(false); }}>Chiqish</button></div>
      <nav className="flex flex-wrap gap-2" aria-label="Bo‘limlar">{TABS.map((t) => <button key={t.key} aria-pressed={t.key === tab.key} className={`btn !min-h-10 ${t.key === tab.key ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab(t)}>{t.label}</button>)}
        <button className={`btn !min-h-10 ${tab.key === "settings" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab({ key: "settings", label: "Sozlamalar", path: "/admin/stats" })}>Sozlamalar</button></nav>
      {err && <p role="alert" className="text-warn">{err}</p>}{ok && <p role="status" className="text-brand">{ok}</p>}
      {tab.key === "settings" ? <Settings run={run} /> : (
        <div className="overflow-x-auto"><table className="w-full border-collapse text-left text-sm">
          <thead><tr>{cols.map((c) => <th key={c} className="border-b border-line p-2">{c}</th>)}{tab.actions && <th className="border-b border-line p-2">Amallar</th>}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i} className="align-top">{cols.map((c) => <td key={c} className="border-b border-line p-2">{cell(r[c])}</td>)}{tab.actions && <td className="flex flex-wrap gap-1 border-b border-line p-2">{tab.actions(r, run)}</td>}</tr>)}</tbody>
        </table>{data && rows.length === 0 && <p className="p-2 text-muted">Ma’lumot yo‘q.</p>}</div>)}
    </div>
  );
}
