import type { Metadata, Viewport } from "next";
import { Manrope } from "next/font/google";
import Script from "next/script";
import Header from "@/components/Header";
import "./globals.css";

const font = Manrope({ subsets: ["latin", "latin-ext", "cyrillic"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "Viloyatga Boramiz — viloyatlararo safar hamrohlari",
  description: "O‘zbekiston viloyatlari o‘rtasida haydovchi va yo‘lovchilarni bog‘laydigan xizmat. Manzilingiz bir, yo‘lingiz bir.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0F5132" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz" className={font.variable}>
      <body>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="afterInteractive" />
        <Header />
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
        <footer className="mt-10 border-t border-line py-6 text-center text-sm text-muted">
          Viloyatga Boramiz · Platforma haydovchi va yo‘lovchini bog‘laydi; narxni haydovchi belgilaydi.
        </footer>
      </body>
    </html>
  );
}
