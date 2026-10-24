import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Noto_Sans_Devanagari, Noto_Sans_Kannada } from "next/font/google";
import "./globals.css";

// Geist Sans + Mono for the document; Noto Sans Kannada and Noto Sans Devanagari for Kannada and Hindi drafts (Geist has neither script). All OFL-1.1.
const sans = Geist({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });
const kannada = Noto_Sans_Kannada({ subsets: ["kannada"], variable: "--font-kannada", display: "swap" });
const devanagari = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-devanagari", display: "swap" });

export const metadata: Metadata = {
  title: "Dhara AI: Agentic Copilot for Fair Renting",
  description: "Works out which law governs a rental, prices unfair clauses, and drafts the counter-proposal the tenant approves.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} ${kannada.variable} ${devanagari.variable}`} suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before first paint. No attribute means "follow the OS". */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('dhara-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
