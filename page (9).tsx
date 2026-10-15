"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import MapView from "@/components/MapView";
import { api, errMsg, getToken } from "@/lib/api";
import { dt, money, placeName } from "@/lib/format";
import { REGION_NAMES } from "@/lib/regions";
import type { Trip } from "@/lib/types";

const KIND: Record<string, string> = { pickup: "Jo‘nash joyi", meeting: "Uchrashuv nuqtasi", dropoff: "Tushirish nuqtasi" };

export default function TripPage() {
  const { id } = useParams<{ id: string }>();
  const [t, setT] = useState<Trip | null>(null);
  const [err, setErr] = useState(""); const [msg, setMsg] = useState("");
  const [seats, setSeats] = useState(1); const [text, setText] = useState("");
  const [contact, setContact] = useState<{ telegram: string | null; phone: string | null } | null>(null);
  const [needConsent, setNeedConsent] = useState(false);
  const [rating, setRating] = useState(5); const [complaint, setComplaint] = useState("");
  const markers = useMemo(() => (t?.locations ?? []).map((l) => ({ lat: l.lat, lon: l.lon, label: KIND[l.kind] })), [t]);

  useEffect(() => { api<Trip>(`/trips/${id}`).then(setT).catch((e) => setErr(errMsg(e))); }, [id]);

  const guard = async (fn: () => Promise<void>) => {
    setMsg("");
    if (!getToken()) return setMsg("Avval tizimga kiring.");
    try { await fn(); } catch (e: any) { if (e?.status === 403 && /rozilik/i.test(e.message)) setNeedConsent(true); setMsg(errMsg(e)); }
  };
  const consent = async () => { await api("/me", { method: "PATCH", body: { contact_consent: true } }); setNeedConsent(false); setMsg("Rozilik qabul qilindi. Amalni qaytadan bajaring."); };
  const request = () => guard(async () => { await api(`/trips/${id}/requests`, { method: "POST", body: { seats, message: text || null } }); setMsg("So‘rov haydovchiga yuborildi. Javob Telegramga keladi."); });
  const getContact = () => guard(async () => setContact(await api(`/trips/${id}/contact`)));
  const review = () => guard(async () => { await api(`/trips/${id}/reviews`, { method: "POST", body: { rating } }); setMsg("Baho qabul qilindi."); });
  const complain = () => guard(async () => { await api("/complaints", { method: "POST", body: { text: complaint, trip_id: Number(id) } }); setComplaint(""); setMsg("Shikoyat yuborildi."); });

  if (err) return <p role="alert" className="text-warn">{err}</p>;
  if (!t) return <p className="text-muted">Yuklanmoqda…</p>;
  const shareText = encodeURIComponent(`${placeName(t.from_region, t.from_city, REGION_NAMES)} → ${placeName(t.to_region, t.to_city, REGION_NAMES)}, ${dt(t.depart_at)}, ${money(t.price_uzs)}`);
  const pageUrl = typeof window !== "undefined" ? encodeURIComponent(window.location.href) : "";

  return (
    <div className="space-y-5">
      <Link href="/trips" className="text-brand underline">← Barcha safarlar</Link>
      <h1 className="text-2xl font-extrabold">{placeName(t.from_region, t.from_city, REGION_NAMES)} → {placeName(t.to_region, t.to_city, REGION_NAMES)}</h1>
      <div className="card space-y-1">
        <p>{dt(t.depart_at)} · bo‘sh joy: {t.seats_free} / {t.seats_total}</p>
        <p className="text-2xl font-extrabold text-brand">{money(t.price_uzs)} <span className="text-base font-medium text-muted">1 yo‘lovchi uchun</span></p>
        <p>{t.driver.name} {t.driver.verified && <b className="text-brand">· Tasdiqlangan</b>} {t.driver.rating && <span className="text-muted">· ★ {t.driver.rating} ({t.driver.rating_count})</span>}</p>
        <p className="text-muted">{t.car}</p>{t.comment && <p>{t.comment}</p>}
      </div>

      <section id="xarita" className="space-y-2">
        <h2 className="text-lg font-bold">Xaritada</h2>
        {t.locations.length ? (<>
          <MapView markers={markers} />
          <ul className="text-muted">{t.locations.map((l) => <li key={l.kind}>{KIND[l.kind]}: {l.address ?? `${l.lat.toFixed(5)}, ${l.lon.toFixed(5)}`} · <a className="text-brand underline" href={`https://www.openstreetmap.org/?mlat=${l.lat}&mlon=${l.lon}#map=16/${l.lat}/${l.lon}`}>OSM</a></li>)}</ul>
        </>) : <p className="text-muted">Haydovchi aniq lokatsiya ko‘rsatmagan.</p>}
        <a className="btn btn-ghost" href={`https://t.me/share/url?url=${pageUrl}&text=${shareText}`}>Telegram orqali ulashish</a>
      </section>

      <section className="card space-y-3">
        <h2 className="text-lg font-bold">Haydovchi bilan bog‘lanish</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <div><label className="label" htmlFor="s">Yo‘lovchilar soni</label><input id="s" type="number" min={1} max={t.seats_free || 1} className="input" value={seats} onChange={(e) => setSeats(Math.max(1, Number(e.target.value) || 1))} /></div>
          <div className="sm:col-span-2"><label className="label" htmlFor="m">Xabar (ixtiyoriy)</label><input id="m" maxLength={300} className="input" value={text} onChange={(e) => setText(e.target.value)} /></div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2"><button className="btn btn-primary" onClick={request}>So‘rov yuborish</button><button className="btn btn-ghost" onClick={getContact}>Kontaktni ko‘rish</button></div>
        {needConsent && <div className="rounded-lg bg-brand-tint p-3"><p>Haydovchi bilan bog‘lanish uchun ismingiz va Telegram profilingiz haydovchiga ko‘rinishiga rozimisiz?</p><button className="btn btn-primary mt-2" onClick={consent}>Roziman</button></div>}
        {contact && <p>{contact.telegram ? <a className="text-brand underline" href={contact.telegram}>Telegramda yozish</a> : "Telegram yo‘q"}{contact.phone && <> · Telefon: <a className="underline" href={`tel:${contact.phone}`}>{contact.phone}</a></>}</p>}
        {msg && <p role="status" className="font-semibold text-brand">{msg}</p>}
      </section>

      <section className="card space-y-3">
        <h2 className="text-lg font-bold">Baholash va shikoyat</h2>
        <p className="text-sm text-muted">Baholash faqat safar tugagandan keyin va qabul qilingan yo‘lovchi uchun ochiq.</p>
        <div className="flex gap-2"><select aria-label="Baho" className="input !w-32" value={rating} onChange={(e) => setRating(Number(e.target.value))}>{[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} ★</option>)}</select><button className="btn btn-ghost" onClick={review}>Baholash</button></div>
        <textarea aria-label="Shikoyat matni" className="input min-h-24 py-2" placeholder="Shikoyat matni (kamida 5 belgi)" value={complaint} onChange={(e) => setComplaint(e.target.value)} />
        <button className="btn btn-danger" disabled={complaint.length < 5} onClick={complain}>Shikoyat yuborish</button>
      </section>
    </div>
  );
}
