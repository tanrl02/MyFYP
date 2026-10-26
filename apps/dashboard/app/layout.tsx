import type { Metadata } from "next";
import "./globals.css";
import StaffIdentity from "./StaffIdentity";
export const metadata: Metadata = { title: "Smart Skin | Queue demo", description: "Local synthetic appointment and queue demonstration" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><StaffIdentity>{children}</StaffIdentity></body></html>;
}
