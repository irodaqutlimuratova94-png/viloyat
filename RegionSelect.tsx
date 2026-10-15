"use client";
import { REGION_NAMES } from "@/lib/regions";

export default function RegionSelect({ id, label, value, onChange, optional = false }: { id: string; label: string; value: string; onChange: (v: string) => void; optional?: boolean }) {
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{optional ? "Hammasi" : "Tanlang"}</option>
        {Object.entries(REGION_NAMES).map(([c, n]) => <option key={c} value={c}>{n}</option>)}
      </select>
    </div>
  );
}
