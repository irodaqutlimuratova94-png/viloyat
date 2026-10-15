"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import RegionSelect from "@/components/RegionSelect";
import TripCard from "@/components/TripCard";
import { api, errMsg, getToken } from "@/lib/api";
import type { Trip } from "@/lib/types";

function Search() {
  const sp = useSearchParams();
  const [f, setF] = useState({
    from_region: sp.get("from_region") ?? "", to_region: sp.get("to_region") ?? "", date: sp.get("date") ?? "",
    min_price: "", max_price: "", min_seats: sp.get("min_seats") ?? "1", time_from: "", time_to: "",
  });
  const [trips, setTrips] = useState<Trip[] | null>(null);
  const [err, setErr] = useState(""); const [note, setNote] = useState("");
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    setErr(""); setTrips(null);
    const t = setTimeout(() => api<Trip[]>("/trips", { params: { ...f, limit: 50 } }).then(setTrips).catch((e) => setErr(errMsg(e))), 250);
    return () => clearTimeout(t);
  }, [f]);

  const demand = async () => {
    if (!getToken()) return setNote("Talab qoldirish uchun avval tizimga kiring.");
    if (!f.from_region || !f.to_region) return setNote("Talab uchun jo‘nash va boriladigan hududni tanlang.");
    try {
      await api("/demands", { method: "POST", body: { from_region: f.from_region, to_region: f.to_region, wanted_date: f.date ? f.date + "T00:00:00" : null, seats: Number(f.min_seats) || 1 } });
      setNote("Talab saqlandi. Shu yo‘nalishdagi haydovchilarga Telegram orqali xabar yuborildi.");
    } catch (e) { setNote(errMsg(e)); }
  };
  const fav = async () => {
    if (!getToken()) return setNote("Sevimlilarga qo‘shish uchun tizimga kiring.");
    try { await api("/favorites", { method: "POST", body: { from_region: f.from_region, to_region: f.to_region } }); setNote("Yo‘nalish sevimlilarga qo‘shildi."); } catch (e) { setNote(errMsg(e)); }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-extrabold">Safar topish</h1>
      <div className="card grid gap-3 sm:grid-cols-3">
        <RegionSelect id="f" label="Qayerdan" value={f.from_region} onChange={set("from_region")} optional />
        <RegionSelect id="t" label="Qayerga" value={f.to_region} onChange={set("to_region")} optional />
        <div><label className="label" htmlFor="d">Sana</label><input id="d" type="date" className="input" value={f.date} onChange={(e) => set("date")(e.target.value)} /></div>
        <div><label className="label" htmlFor="mp">Narx dan (so‘m)</label><input id="mp" inputMode="numeric" className="input" value={f.min_price} onChange={(e) => set("min_price")(e.target.value.replace(/\D/g, ""))} /></div>
        <div><label className="label" htmlFor="xp">Narx gacha (so‘m)</label><input id="xp" inputMode="numeric" className="input" value={f.max_price} onChange={(e) => set("max_price")(e.target.value.replace(/\D/g, ""))} /></div>
        <div><label className="label" htmlFor="ms">Kamida bo‘sh joy</label><input id="ms" type="number" min={1} max={8} className="input" value={f.min_seats} onChange={(e) => set("min_seats")(e.target.value)} /></div>
        <div><label className="label" htmlFor="t1">Jo‘nash vaqti: dan</label><input id="t1" type="time" className="input" value={f.time_from} onChange={(e) => set("time_from")(e.target.value)} /></div>
        <div><label className="label" htmlFor="t2">gacha</label><input id="t2" type="time" className="input" value={f.time_to} onChange={(e) => set("time_to")(e.target.value)} /></div>
      </div>
      {err && <p role="alert" className="text-warn">{err}</p>}
      {trips === null && !err && <p className="text-muted">Qidirilmoqda…</p>}
      {trips && trips.length === 0 && (
        <div className="card space-y-3">
          <p className="font-semibold">Mos safar topilmadi.</p>
          <p className="text-muted">Talab qoldiring: shu yo‘nalishda safar e’lon qilgan haydovchilarga Telegram orqali xabar boradi.</p>
          <div className="grid gap-2 sm:grid-cols-2"><button className="btn btn-primary" onClick={demand}>Talab yaratish</button><button className="btn btn-ghost" onClick={fav}>Yo‘nalishni sevimlilarga qo‘shish</button></div>
        </div>
      )}
      {note && <p role="status" className="text-brand">{note}</p>}
      <div className="grid gap-3 sm:grid-cols-2">{trips?.map((t) => <TripCard key={t.id} t={t} />)}</div>
    </div>
  );
}

export default function Page() { return <Suspense fallback={<p>Yuklanmoqda…</p>}><Search /></Suspense>; }
