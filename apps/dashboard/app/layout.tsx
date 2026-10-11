import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Smart Skin | Queue demo", description: "Local synthetic appointment and queue demonstration" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
