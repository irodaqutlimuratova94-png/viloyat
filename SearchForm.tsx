"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import RegionSelect from "./RegionSelect";

export default function SearchForm() {
  const r = useRouter();
  const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const [date, setDate] = useState(""); const [pax, setPax] = useState(1);
  const go = () => {
    const q = new URLSearchParams();
    if (from) q.set("from_region", from); if (to) q.set("to_region", to);
    if (date) q.set("date", date); q.set("min_seats", String(pax));
    r.push(`/trips?${q}`);
  };
  return (
    <div className="card grid gap-3 sm:grid-cols-2">
      <RegionSelect id="from" label="Qayerdan yo‘lga chiqasiz?" value={from} onChange={setFrom} />
      <RegionSelect id="to" label="Qayerga borasiz?" value={to} onChange={setTo} />
      <div><label htmlFor="date" className="label">Jo‘nash sanasi</label><input id="date" type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} /></div>
      <div><label htmlFor="pax" className="label">Yo‘lovchilar soni</label><input id="pax" type="number" min={1} max={8} className="input" value={pax} onChange={(e) => setPax(Math.max(1, Number(e.target.value) || 1))} /></div>
      <button onClick={go} className="btn btn-primary sm:col-span-2">Safar topish</button>
      <Link href="/driver" className="btn btn-ghost sm:col-span-2">Haydovchi sifatida safar joylash</Link>
    </div>
  );
}
