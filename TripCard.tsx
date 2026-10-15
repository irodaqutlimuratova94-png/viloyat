import Link from "next/link";
import { dt, money, placeName } from "@/lib/format";
import { REGION_NAMES } from "@/lib/regions";
import type { Trip } from "@/lib/types";

export default function TripCard({ t }: { t: Trip }) {
  const d = t.driver;
  return (
    <article className="card flex flex-col gap-2">
      <h3 className="text-lg font-bold">
        {placeName(t.from_region, t.from_city, REGION_NAMES)} → {placeName(t.to_region, t.to_city, REGION_NAMES)}
      </h3>
      <p className="text-muted">{dt(t.depart_at)} · bo‘sh joy: {t.seats_free}</p>
      <p className="text-xl font-extrabold text-brand">{money(t.price_uzs)} <span className="text-sm font-medium text-muted">1 yo‘lovchi uchun</span></p>
      <p>
        <span className="font-semibold">{d.name}</span>
        {d.verified && <span className="ml-1 rounded bg-brand-tint px-1.5 py-0.5 text-sm font-semibold text-brand">Tasdiqlangan</span>}
        {d.rating && <span className="ml-2 text-muted">★ {d.rating} ({d.rating_count})</span>}
      </p>
      <p className="text-muted">{t.car}</p>
      {t.comment && <p>{t.comment}</p>}
      <div className="mt-1 grid gap-2 sm:grid-cols-2">
        <Link href={`/trips/${t.id}`} className="btn btn-primary">Haydovchi bilan bog‘lanish</Link>
        <Link href={`/trips/${t.id}#xarita`} className="btn btn-ghost">Xaritada ko‘rish</Link>
      </div>
    </article>
  );
}
