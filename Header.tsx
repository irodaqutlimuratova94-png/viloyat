"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";

export default function Header() {
  const [logged, setLogged] = useState(false);
  useEffect(() => setLogged(!!getToken()), []);
  return (
    <header className="border-b border-line bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="text-lg font-extrabold text-brand">Viloyatga Boramiz</Link>
        <nav className="flex items-center gap-1 text-sm font-semibold sm:gap-3 sm:text-base">
          <Link href="/trips" className="px-2 py-2">Safar topish</Link>
          <Link href="/driver" className="px-2 py-2">Haydovchi</Link>
          <Link href={logged ? "/me" : "/login"} className="btn btn-ghost !min-h-10 !px-3">{logged ? "Kabinet" : "Kirish"}</Link>
        </nav>
      </div>
    </header>
  );
}
