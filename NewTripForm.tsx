"use client";
import { useRef, useState } from "react";
import MapView from "./MapView";
import RegionSelect from "./RegionSelect";
import { api, errMsg } from "@/lib/api";
import { useCities } from "@/lib/hooks";
import type { LatLng } from "@/lib/map";

type Kind = "pickup" | "meeting" | "dropoff";
const KIND: Record<Kind, string> = { pickup: "Jo‘nash lokatsiyasi", meeting: "Uchrashuv nuqtasi", dropoff: "Tushirish nuqtasi" };

export default function NewTripForm({ onCreated }: { onCreated: () => void }) {
  const cities = useCities();
  const idem = useRef(crypto.randomUUID());
  const [f, setF] = useState({ from_region: "", from_city: "", to_region: "", to_city: "", depart_at: "", seats_total: 3, price_uzs: "", comment: "", has_return: false, return_depart_at: "" });
  const [pts, setPts] = useState<Partial<Record<Kind, LatLng>>>({});
  const [active, setActive] = useState<Kind>("pickup");
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  const set = (k: keyof typeof f, v: string | number | boolean) => setF((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    setBusy(true); setErr(""); setOk("");
    try {
      const loc = (k: Kind) => (pts[k] ? { lat: pts[k]!.lat, lon: pts[k]!.lon } : null);
      const r = await api<{ id: number }[]>("/trips", {
        method: "POST", headers: { "Idempotency-Key": idem.current },
        body: {
          from_region: f.from_region, from_city: f.from_city || null, to_region: f.to_region, to_city: f.to_city || null,
          depart_at: f.depart_at, seats_total: Number(f.seats_total), price_uzs: Number(f.price_uzs), comment: f.comment || null,
          pickup: loc("pickup"), meeting: loc("meeting"), dropoff: loc("dropoff"),
          has_return: f.has_return, return_depart_at: f.has_return ? f.return_depart_at : null,
        },
      });
      setOk(`Safar e’lon qilindi. Identifikator: #${r.map((x) => x.id).join(", #")}`);
      idem.current = crypto.randomUUID(); onCreated();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  const city = (id: string, label: string, region: string, val: string, key: "from_city" | "to_city") => (
    <div><label className="label" htmlFor={id}>{label}</label>
      <input id={id} list={id + "-l"} className="input" value={val} onChange={(e) => set(key, e.target.value)} placeholder="Shahar yoki tuman" />
      <datalist id={id + "-l"}>{(cities[region] ?? []).map((c) => <option key={c} value={c} />)}</datalist></div>
  );
  const valid = f.from_region && f.to_region && f.depart_at && Number(f.price_uzs) > 0 && (!f.has_return || f.return_depart_at);

  return (
    <div className="card space-y-4">
      <h2 className="text-lg font-bold">Yangi safar e’lon qilish</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <RegionSelect id="nf" label="Qayerdan jo‘naysiz?" value={f.from_region} onChange={(v) => set("from_region", v)} />
        {city("nfc", "Jo‘nash shahri/tumani", f.from_region, f.from_city, "from_city")}
        <RegionSelect id="nt" label="Qayerga borasiz?" value={f.to_region} onChange={(v) => set("to_region", v)} />
        {city("ntc", "Boriladigan shahar/tuman", f.to_region, f.to_city, "to_city")}
        <div><label className="label" htmlFor="dt">Jo‘nash sanasi va vaqti (Toshkent vaqti)</label><input id="dt" type="datetime-local" className="input" value={f.depart_at} onChange={(e) => set("depart_at", e.target.value)} /></div>
        <div><label className="label" htmlFor="st">Bo‘sh o‘rinlar soni</label><input id="st" type="number" min={1} max={8} className="input" value={f.seats_total} onChange={(e) => set("seats_total", Number(e.target.value))} /></div>
        <div><label className="label" htmlFor="pr">Bir yo‘lovchi uchun narx (so‘m) — o‘zingiz belgilaysiz</label><input id="pr" inputMode="numeric" className="input" value={f.price_uzs} onChange={(e) => set("price_uzs", e.target.value.replace(/\D/g, ""))} /></div>
        <div><label className="label" htmlFor="cm">Qo‘shimcha izoh</label><input id="cm" maxLength={500} className="input" value={f.comment} onChange={(e) => set("comment", e.target.value)} /></div>
      </div>
      <label className="flex items-center gap-3"><input type="checkbox" className="h-6 w-6" checked={f.has_return} onChange={(e) => set("has_return", e.target.checked)} /> Qaytish safari ham bor</label>
      {f.has_return && <div><label className="label" htmlFor="rd">Qaytish sanasi va vaqti</label><input id="rd" type="datetime-local" className="input sm:w-72" value={f.return_depart_at} onChange={(e) => set("return_depart_at", e.target.value)} /></div>}

      <fieldset className="space-y-2">
        <legend className="label">Xaritadan nuqta belgilash: avval turini tanlang, keyin xaritaga bosing</legend>
        <div className="flex flex-wrap gap-2">{(Object.keys(KIND) as Kind[]).map((k) => (
          <button key={k} type="button" aria-pressed={active === k} onClick={() => setActive(k)} className={`btn !min-h-10 ${active === k ? "btn-primary" : "btn-ghost"}`}>{KIND[k]}{pts[k] ? " ✓" : ""}</button>))}</div>
        <MapView height={280} onPick={(p) => setPts((s) => ({ ...s, [active]: p }))} markers={Object.entries(pts).map(([k, p]) => ({ ...p!, label: KIND[k as Kind] }))} />
      </fieldset>

      {err && <p role="alert" className="text-warn">{err}</p>}{ok && <p role="status" className="font-semibold text-brand">{ok}</p>}
      <button className="btn btn-primary w-full" disabled={busy || !valid} onClick={submit}>{busy ? "Yuborilmoqda…" : "Safarni e’lon qilish"}</button>
    </div>
  );
}
