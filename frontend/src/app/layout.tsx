import type { Metadata } from "next";
import { DM_Sans, Oswald } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

const oswald = Oswald({
  subsets: ["latin"],
  variable: "--font-oswald",
});

export const metadata: Metadata = {
  title: "BGM Travels | Belgaum to Bengaluru bus tickets",
  description: "Book comfortable intercity bus tickets between Belgaum and Bengaluru with BGM Travels.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${dmSans.variable} ${oswald.variable} font-sans antialiased`}>{children}</body>
    </html>
  );
}
