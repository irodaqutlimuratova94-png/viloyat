"use client";
import { useEffect, useState } from "react";
import { api, getToken } from "./api";
import type { Me } from "./types";

export function useMe() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = async () => {
    if (!getToken()) { setMe(null); setLoading(false); return; }
    try { setMe(await api<Me>("/me")); } catch { setMe(null); }
    setLoading(false);
  };
  useEffect(() => { reload(); }, []);
  return { me, loading, reload };
}

export function useCities() {
  const [cities, setCities] = useState<Record<string, string[]>>({});
  useEffect(() => {
    api<{ code: string; cities: string[] }[]>("/regions").then((r) => setCities(Object.fromEntries(r.map((x) => [x.code, x.cities])))).catch(() => {});
  }, []);
  return cities;
}
