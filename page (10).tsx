"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import NewTripForm from "@/components/NewTripForm";
import { api, errMsg } from "@/lib/api";
import { dt, money, placeName } from "@/lib/format";
import { useMe } from "@/lib/hooks";
import { REGION_NAMES } from "@/lib/regions";
import type { Plan, Trip } from "@/lib/types";

type Drv = { id: number; verification: string; vehicles: { id: number; make_model: string; plate: string; seats: number }[]; subscription: { active: boolean; kind: string | null; ends_at: string | null; days_left: number } };
type In = { id: number; trip_id: number; passenger: string; seats: number; message: string | null; status: string };

function Register({ onDone }: { onDone: () => void }) {
  const [f, setF] = useState({ full_name: "", make_model: "", plate: "", seats: 5 }); const [err, setErr] = useState("");
  const set = (k: keyof typeof f, v: string | number) => setF((p) => ({ ...p, [k]: v }));
  const go = async () => { try { await api("/drivers/register", { method: "POST", body: f }); onDone(); } catch (e) { setErr(errMsg(e)); } };
  return (
    <div className="card mx-auto max-w-lg space-y-3">
      <h1 className="text-2xl font-extrabold">Haydovchi bo‘lish</h1>
      <p className="text-muted">Ro‘yxatdan o‘tgan kundan boshlab 30 kun bepul.</p>
      <div><label className="label" htmlFor="n">Ism va familiya</label><input id="n" className="input" value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></div>
      <div><label className="label" htmlFor="m">Avtomobil rusumi va modeli</label><input id="m" className="input" placeholder="Chevrolet Malibu" value={f.make_model} onChange={(e) => set("make_model", e.target.value)} /></div>
      <div><label className="label" htmlFor="p">Davlat raqami</label><input id="p" className="input" placeholder="01A123BC" value={f.plate} onChange={(e) => set("plate", e.target.value)} /></div>
      <div><label className="label" htmlFor="s">O‘rindiqlar soni (haydovchi bilan)</label><input id="s" type="number" min={2} max={8} className="input" value={f.seats} onChange={(e) => set("seats", Number(e.target.value))} /></div>
      <p className="text-sm text-muted">Ro‘yxatdan o‘tish orqali yo‘lovchilar siz bilan bog‘lanishiga rozilik berasiz. Telefon raqamni tasdiqlash — Telegram-botda.</p>
      {err && <p role="alert" className="text-warn">{err}</p>}
      <button className="btn btn-primary w-full" onClick={go}>Ro‘yxatdan o‘tish</button>
    </div>
  );
}

export default function Driver() {
  const { me, loading, reload } = useMe();
  const [drv, setDrv] = useState<Drv | null>(null); const [trips, setTrips] = useState<Trip[]>([]);
  const [reqs, setReqs] = useState<In[]>([]); const [plans, setPlans] = useState<Plan[]>([]); const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setDrv(await api<Drv>("/drivers/me"));
      setTrips(await api<Trip[]>("/trips/mine")); setReqs(await api<In[]>("/drivers/me/requests")); setPlans(await api<Plan[]>("/plans"));
    } catch (e) { setErr(errMsg(e)); }
  }, []);
  useEffect(() => { if (me?.is_driver) load(); }, [me, load]);

  if (loading) return <p>Yuklanmoqda…</p>;
  if (!me) return <p>Davom etish uchun <Link className="text-brand underline" href="/login">tizimga kiring</Link>.</p>;
  if (!me.is_driver) return <Register onDone={() => reload()} />;
  if (!drv) return <p>{err || "Yuklanmoqda…"}</p>;
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); setErr(""); await load(); } catch (e) { setErr(errMsg(e)); } };
  const pay = (id: number) => act(async () => { const r = await api<{ pay_url: string }>("/payments", { method: "POST", body: { plan_id: id } }); location.href = r.pay_url; });
  const s = drv.subscription;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-extrabold">Haydovchi kabineti</h1>
      <div className={`card space-y-2 ${s.active ? "" : "border-warn"}`}>
        <p className="font-semibold">{s.active ? `${s.kind === "trial" ? "Bepul sinov" : "Pullik obuna"}: ${dt(s.ends_at!)} gacha (${s.days_left} kun)` : "Faol obuna yo‘q: yangi safar e’lon qila olmaysiz. Avvalgi safar va profilingiz saqlanadi."}</p>
        <p className="text-muted">Tekshiruv holati: {drv.verification === "verified" ? "tasdiqlangan" : drv.verification === "rejected" ? "rad etilgan" : "tekshirilmoqda"} · Avtomobil: {drv.vehicles[0]?.make_model} ({drv.vehicles[0]?.plate})</p>
        {plans.length ? <div className="grid gap-2 sm:grid-cols-3">{plans.map((p) => <button key={p.id} className="btn btn-ghost" onClick={() => pay(p.id)}>{p.name}: {money(p.price_uzs)}</button>)}</div> : <p className="text-sm text-muted">Tariflar hali belgilanmagan.</p>}
      </div>
      {err && <p role="alert" className="text-warn">{err}</p>}

      {s.active ? <NewTripForm onCreated={load} /> : null}

      <section><h2 className="mb-2 text-lg font-bold">Kelgan so‘rovlar</h2>
        {reqs.length === 0 ? <p className="text-muted">So‘rovlar yo‘q.</p> : <ul className="space-y-2">{reqs.map((r) => (
          <li key={r.id} className="card flex flex-wrap items-center justify-between gap-2">
            <span>Safar #{r.trip_id}: <b>{r.passenger}</b>, {r.seats} o‘rin{r.message ? ` — ${r.message}` : ""} ({r.status})</span>
            {r.status === "pending" && <span className="flex gap-2"><button className="btn btn-primary !min-h-10" onClick={() => act(() => api(`/requests/${r.id}`, { method: "PATCH", body: { status: "accepted" } }))}>Qabul</button><button className="btn btn-danger !min-h-10" onClick={() => act(() => api(`/requests/${r.id}`, { method: "PATCH", body: { status: "rejected" } }))}>Rad</button></span>}
          </li>))}</ul>}
      </section>

      <section><h2 className="mb-2 text-lg font-bold">Mening safarlarim</h2>
        {trips.length === 0 ? <p className="text-muted">Hali safar e’lon qilmagansiz.</p> : <ul className="space-y-2">{trips.map((t) => (
          <li key={t.id} className="card flex flex-wrap items-center justify-between gap-2">
            <span>#{t.id} · {placeName(t.from_region, t.from_city, REGION_NAMES)} → {placeName(t.to_region, t.to_city, REGION_NAMES)} · {dt(t.depart_at)} · {money(t.price_uzs)} · bo‘sh: {t.seats_free} · <b>{t.status}</b></span>
            {t.status === "active" && <span className="flex gap-2">
              <button className="btn btn-ghost !min-h-10" disabled={t.seats_free === 0} onClick={() => act(() => api(`/trips/${t.id}`, { method: "PATCH", body: { seats_free: t.seats_free - 1 } }))}>− joy</button>
              <button className="btn btn-ghost !min-h-10" disabled={t.seats_free >= t.seats_total} onClick={() => act(() => api(`/trips/${t.id}`, { method: "PATCH", body: { seats_free: t.seats_free + 1 } }))}>+ joy</button>
              <button className="btn btn-danger !min-h-10" onClick={() => confirm("Safarni bekor qilasizmi? Yo‘lovchilarga xabar yuboriladi.") && act(() => api(`/trips/${t.id}`, { method: "DELETE" }))}>Bekor qilish</button></span>}
          </li>))}</ul>}
      </section>
    </div>
  );
}
