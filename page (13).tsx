"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, errMsg, setToken } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const box = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState("");
  const bot = process.env.NEXT_PUBLIC_BOT_USERNAME;

  useEffect(() => {
    const finish = async (path: string, body: unknown) => {
      try {
        const r = await api<{ access_token: string }>(path, { method: "POST", body });
        setToken(r.access_token);
        router.push("/me");
        router.refresh();
      } catch (e) { setErr(errMsg(e)); }
    };
    const w = window as any;
    if (w.Telegram?.WebApp?.initData) finish("/auth/telegram-webapp", { init_data: w.Telegram.WebApp.initData }); // Mini App ichida
    w.onTelegramAuth = (user: unknown) => finish("/auth/telegram", user);
    if (bot && box.current) {
      const s = document.createElement("script");
      s.src = "https://telegram.org/js/telegram-widget.js?22";
      s.async = true;
      s.setAttribute("data-telegram-login", bot);
      s.setAttribute("data-size", "large");
      s.setAttribute("data-radius", "8");
      s.setAttribute("data-onauth", "onTelegramAuth(user)");
      s.setAttribute("data-request-access", "write");
      box.current.appendChild(s);
    }
  }, [bot, router]);

  return (
    <div className="mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-extrabold">Tizimga kirish</h1>
      <p className="text-muted">Telegram orqali kiring. Parol kerak emas.</p>
      <div ref={box} className="min-h-12" />
      {!bot && <p className="text-warn">NEXT_PUBLIC_BOT_USERNAME sozlanmagan: kirish tugmasi chiqmaydi.</p>}
      {err && <p role="alert" className="text-warn">{err}</p>}
      <p className="text-sm text-muted">Telefon raqam botda “Haydovchi bo‘lish” jarayonida tasdiqlanadi.</p>
    </div>
  );
}
