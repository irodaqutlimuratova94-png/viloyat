import { leafletProvider } from "./leaflet";
import type { MapProvider } from "./types";

// Provayderni almashtirish: yangi MapProvider yozib, shu yerda tanlang.
export function getMapProvider(): MapProvider {
  switch (process.env.NEXT_PUBLIC_MAP_PROVIDER) {
    default:
      return leafletProvider;
  }
}
export * from "./types";
