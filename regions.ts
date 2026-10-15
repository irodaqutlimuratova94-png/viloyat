// Hudud kodlari backend (app/regions.py) bilan bir xil. Shahar/tumanlar esa /regions API'dan olinadi.
export const REGION_NAMES: Record<string, string> = {
  toshkent_shahri: "Toshkent shahri", toshkent: "Toshkent viloyati", samarqand: "Samarqand viloyati",
  buxoro: "Buxoro viloyati", andijon: "Andijon viloyati", fargona: "Farg‘ona viloyati",
  namangan: "Namangan viloyati", qashqadaryo: "Qashqadaryo viloyati", surxondaryo: "Surxondaryo viloyati",
  jizzax: "Jizzax viloyati", sirdaryo: "Sirdaryo viloyati", navoiy: "Navoiy viloyati",
  xorazm: "Xorazm viloyati", qoraqalpogiston: "Qoraqalpog‘iston Respublikasi",
};
export const REGION_CODES = Object.keys(REGION_NAMES);
