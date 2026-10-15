export type LatLng = { lat: number; lon: number };
export type MarkerSpec = LatLng & { label?: string };
export interface MapHandle {
  setMarkers(markers: MarkerSpec[]): void;
  onPick(cb: (p: LatLng) => void): void;
  destroy(): void;
}
export interface MapProvider {
  create(el: HTMLElement, opts: { center: LatLng; zoom: number }): Promise<MapHandle>;
}
