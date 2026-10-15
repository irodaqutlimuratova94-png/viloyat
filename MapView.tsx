"use client";
import { useEffect, useRef } from "react";
import { getMapProvider, type LatLng, type MapHandle, type MarkerSpec } from "@/lib/map";

const UZ_CENTER: LatLng = { lat: 41.3, lon: 64.6 };

export default function MapView({ markers = [], onPick, height = 320 }: { markers?: MarkerSpec[]; onPick?: (p: LatLng) => void; height?: number }) {
  const el = useRef<HTMLDivElement>(null);
  const handle = useRef<MapHandle | null>(null);
  const latest = useRef({ markers, onPick });
  latest.current = { markers, onPick };

  useEffect(() => {
    let dead = false;
    getMapProvider()
      .create(el.current!, { center: UZ_CENTER, zoom: 6 })
      .then((h) => {
        if (dead) return h.destroy();
        handle.current = h;
        h.onPick((p) => latest.current.onPick?.(p));
        h.setMarkers(latest.current.markers);
      });
    return () => { dead = true; handle.current?.destroy(); handle.current = null; };
  }, []);

  useEffect(() => { handle.current?.setMarkers(markers); }, [markers]);

  return <div ref={el} style={{ height }} className="w-full rounded-lg border border-line" role="application" aria-label="Xarita" />;
}
