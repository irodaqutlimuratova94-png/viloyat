import type { MapProvider, MarkerSpec } from "./types";

// OpenStreetMap plitkalari. Ommaviy OSM serveri og'ir yuklama uchun mo'ljallanmagan:
// production'da o'z tile-serveringiz yoki tijoriy provayder (MapTiler va h.k.) URL'ini qo'ying.
const TILES = process.env.NEXT_PUBLIC_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export const leafletProvider: MapProvider = {
  async create(el, { center, zoom }) {
    const L = (await import("leaflet")).default;
    await import("leaflet/dist/leaflet.css");
    const map = L.map(el).setView([center.lat, center.lon], zoom);
    L.tileLayer(TILES, { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    let pick: ((p: { lat: number; lon: number }) => void) | null = null;
    map.on("click", (e) => pick?.({ lat: e.latlng.lat, lon: e.latlng.lng }));
    return {
      setMarkers(markers: MarkerSpec[]) {
        layer.clearLayers();
        markers.forEach((m) => {
          const c = L.circleMarker([m.lat, m.lon], { radius: 9, color: "#0F5132", fillColor: "#0F5132", fillOpacity: 0.85 }).addTo(layer);
          if (m.label) c.bindTooltip(m.label, { permanent: false });
        });
        if (markers.length) map.fitBounds(L.latLngBounds(markers.map((m) => [m.lat, m.lon] as [number, number])), { maxZoom: 14, padding: [30, 30] });
      },
      onPick(cb) { pick = cb; },
      destroy() { map.remove(); },
    };
  },
};
