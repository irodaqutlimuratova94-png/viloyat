export type Loc = { kind: "pickup" | "meeting" | "dropoff"; lat: number; lon: number; address: string | null };
export type Trip = {
  id: number; from_region: string; from_city: string | null; to_region: string; to_city: string | null;
  depart_at: string; seats_total: number; seats_free: number; price_uzs: number; comment: string | null;
  status: string; car: string; locations: Loc[];
  driver: { id: number; name: string; photo_url: string | null; rating: number | null; rating_count: number; verified: boolean };
};
export type Me = {
  id: number; full_name: string; username: string | null; has_phone: boolean; phone_verified: boolean;
  contact_consent: boolean; is_driver: boolean; driver_verification: string | null;
  subscription: { kind: string; ends_at: string } | null;
};
export type Plan = { id: number; code: string; name: string; days: number; price_uzs: number };
