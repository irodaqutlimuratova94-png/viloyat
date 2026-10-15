"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, errMsg, setToken } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import { REGION_NAMES } from "@/lib/regions";

type Req = { id: number; trip_id: number | null; seats: number; status: string; from_region: string | null; to_region: string | null };
type Fav = { id: number; from_region: string; to_region: string };
const ST: Record<string, string> = { pending: "Kutilmoqda", accepted: "Qabul qilindi", rejected: "Rad etildi", cancelled: "Bekor qilindi", open: "Talab ochiq" };

export default function Me() {
  const { me, loading, reload } = useMe();
  const [reqs, setReqs] = useState<Req[]>([]); const [favs, setFavs] = useState<Fav[]>([]); const [err, setErr] = useState("");
  const load = () => { api<Req[]>("/me/requests").then(setReqs).catch(() => {}); api<Fav[]>("/favorites").then(setFavs).catch(() => {}); };
  useEffect(() => { if (me) load(); }, [me]);

  if (loading) return <p>Yuklanmoqda…</p>;
  if (!me) return <p>Kabinetni ko‘rish uchun <Link className="text-brand underline" href="/login">tizimga kiring</Link>.</p>;
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); setErr(""); load(); reload(); } catch (e) { setErr(errMsg(e)); } };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-extrabold">{me.full_name}</h1>
      <div className="card space-y-2">
        <label className="flex items-center gap-3"><input type="checkbox" className="h-6 w-6" checked={me.contact_consent} onChange={(e) => act(() => api("/me", { method: "PATCH", body: { contact_consent: e.target.checked } }))} /> Haydovchi bilan bog‘lanish uchun aloqa roziligi</label>
        <p className="text-muted">Telefon: {me.phone_verified ? "tasdiqlangan" : "tasdiqlanmagan (botda “Haydovchi bo‘lish” orqali)"}</p>
        <Link className="btn btn-ghost" href="/driver">Haydovchi kabineti</Link>
      </div>
      {err && <p role="alert" className="text-warn">{err}</p>}
      <section><h2 className="mb-2 text-lg font-bold">Mening so‘rovlarim</h2>
        {reqs.length === 0 ? <p className="text-muted">So‘rovlar yo‘q.</p> : <ul className="space-y-2">{reqs.map((r) => (
          <li key={r.id} className="card flex flex-wrap items-center justify-between gap-2">
            <span>{r.trip_id ? <Link className="text-brand underline" href={`/trips/${r.trip_id}`}>Safar #{r.trip_id}</Link> : `${REGION_NAMES[r.from_region ?? ""]} → ${REGION_NAMES[r.to_region ?? ""]} (talab)`} · {r.seats} o‘rin · {ST[r.status] ?? r.status}</span>
            {["pending", "accepted", "open"].includes(r.status) && <button className="btn btn-danger !min-h-10" onClick={() => act(() => api(`/requests/${r.id}`, { method: "DELETE" }))}>Bekor qilish</button>}
          </li>))}</ul>}
      </section>
      <section><h2 className="mb-2 text-lg font-bold">Sevimli yo‘nalishlar</h2>
        {favs.length === 0 ? <p className="text-muted">Hali yo‘q.</p> : <ul className="space-y-2">{favs.map((f) => (
          <li key={f.id} className="card flex items-center justify-between gap-2"><Link className="font-semibold text-brand underline" href={`/trips?from_region=${f.from_region}&to_region=${f.to_region}`}>{REGION_NAMES[f.from_region]} → {REGION_NAMES[f.to_region]}</Link><button className="btn btn-danger !min-h-10" onClick={() => act(() => api(`/favorites/${f.id}`, { method: "DELETE" }))}>O‘chirish</button></li>))}</ul>}
      </section>
      <button className="btn btn-ghost" onClick={() => { setToken(null); location.href = "/"; }}>Chiqish</button>
    </div>
  );
}
