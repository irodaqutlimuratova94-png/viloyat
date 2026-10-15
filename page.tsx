import Link from "next/link";
import SearchForm from "@/components/SearchForm";
import TripCard from "@/components/TripCard";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { REGION_NAMES } from "@/lib/regions";
import type { Plan, Trip } from "@/lib/types";

export const dynamic = "force-dynamic";

async function safe<T>(p: Promise<T>, fallback: T): Promise<T> {
  try { return await p; } catch { return fallback; }
}

const FAQ: [string, string][] = [
  ["Yo‘lovchi uchun xizmat pullikmi?", "Yo‘q. Safar qidirish va haydovchi bilan bog‘lanish yo‘lovchilar uchun bepul."],
  ["Narxni kim belgilaydi?", "Narxni faqat haydovchi belgilaydi. Platforma narxga aralashmaydi va o‘zi narx qo‘ymaydi."],
  ["Haydovchi uchun obuna qanday ishlaydi?", "Ro‘yxatdan o‘tgan kundan boshlab 30 kun bepul. Keyin yangi safar e’lon qilish uchun tarif tanlanadi. Eski safarlar va profil saqlanadi."],
  ["Mos safar topilmasa nima qilaman?", "Talab qoldiring: shu yo‘nalishda safar e’lon qilgan haydovchilarga Telegram orqali xabar boradi."],
  ["Telefon raqamim hammaga ko‘rinadimi?", "Yo‘q. Kontaktlar faqat tizimga kirgan va rozilik bergan foydalanuvchiga ko‘rsatiladi."],
];

export default async function Home() {
  const [popular, upcoming, plans] = await Promise.all([
    safe(api<{ from_region: string; to_region: string; trips: number; min_price_uzs: number }[]>("/popular-routes"), []),
    safe(api<Trip[]>("/trips", { params: { limit: 4 } }), []),
    safe(api<Plan[]>("/plans"), []),
  ]);
  const bot = process.env.NEXT_PUBLIC_BOT_USERNAME;
  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <h1 className="text-3xl font-extrabold leading-tight text-brand sm:text-4xl">Manzilingiz bir, yo‘lingiz bir.</h1>
        <p className="max-w-prose text-lg text-muted">Viloyatlar o‘rtasida qatnaydigan haydovchilar bilan yo‘lovchilarni bog‘laymiz.</p>
        <SearchForm />
      </section>

      <section>
        <h2 className="mb-3 text-xl font-bold">Ommabop yo‘nalishlar</h2>
        {popular.length === 0 ? <p className="text-muted">Hozircha faol yo‘nalishlar yo‘q. Birinchi safarni siz e’lon qiling.</p> : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {popular.map((p) => (
              <li key={p.from_region + p.to_region}>
                <Link className="card flex items-center justify-between hover:bg-brand-tint" href={`/trips?from_region=${p.from_region}&to_region=${p.to_region}`}>
                  <span className="font-semibold">{REGION_NAMES[p.from_region]} → {REGION_NAMES[p.to_region]}</span>
                  <span className="text-sm text-muted">{p.trips} ta · {money(p.min_price_uzs)} dan</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-xl font-bold">Yaqinlashayotgan safarlar</h2>
        {upcoming.length === 0 ? <p className="text-muted">Yaqin kunlarda e’lon qilingan safar yo‘q.</p> : <div className="grid gap-3 sm:grid-cols-2">{upcoming.map((t) => <TripCard key={t.id} t={t} />)}</div>}
      </section>

      <section>
        <h2 className="mb-3 text-xl font-bold">Qanday ishlaydi</h2>
        <ol className="grid gap-3 sm:grid-cols-3">
          <li className="card"><b>Yo‘nalishni tanlang.</b><br /><span className="text-muted">Qayerdan, qayerga va qaysi kuni.</span></li>
          <li className="card"><b>Haydovchini tanlang.</b><br /><span className="text-muted">Narx, vaqt, reyting va avtomobilni solishtiring.</span></li>
          <li className="card"><b>Kelishib oling.</b><br /><span className="text-muted">So‘rov yuboring yoki Telegram orqali yozing.</span></li>
        </ol>
      </section>

      <section className="card space-y-2 bg-brand-tint">
        <h2 className="text-xl font-bold">Haydovchilar uchun obuna</h2>
        <p>Birinchi 30 kun bepul. Keyin yangi safar e’lon qilish uchun tarif tanlanadi; avvalgi safarlar va profil o‘chirilmaydi.</p>
        {plans.length > 0 ? (
          <ul className="list-disc pl-5">{plans.map((p) => <li key={p.id}>{p.name}: {money(p.price_uzs)} / {p.days} kun</li>)}</ul>
        ) : <p className="text-muted">Tarif narxlari tez orada e’lon qilinadi.</p>}
        <Link href="/driver" className="btn btn-primary mt-2 w-full sm:w-auto">Haydovchi bo‘lish</Link>
      </section>

      <section>
        <h2 className="mb-3 text-xl font-bold">Savol-javob</h2>
        <div className="space-y-2">
          {FAQ.map(([q, a]) => (
            <details key={q} className="card"><summary className="cursor-pointer font-semibold">{q}</summary><p className="mt-2 text-muted">{a}</p></details>
          ))}
        </div>
      </section>

      <section id="aloqa" className="card">
        <h2 className="mb-1 text-xl font-bold">Aloqa</h2>
        <p>Savollar bo‘yicha Telegram-botimizdagi “Yordam” bo‘limiga yozing.</p>
        {bot && <a className="btn btn-ghost mt-3" href={`https://t.me/${bot}`}>Telegram-botni ochish</a>}
      </section>
    </div>
  );
}
