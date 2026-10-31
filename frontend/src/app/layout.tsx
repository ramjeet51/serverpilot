import type { Metadata } from "next";
import { Fraunces, Outfit } from "next/font/google";

import { Providers } from "@/components/providers";
import { env } from "@/lib/env";

import "./globals.css";

const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });
const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces" });

export const metadata: Metadata = {
  title: env.appName,
  description: "Linux server management control plane",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} ${fraunces.variable} antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
