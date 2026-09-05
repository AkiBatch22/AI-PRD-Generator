import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Context — Product Copilot",
  description:
    "Ground product decisions in organization knowledge. Discover, define, and review engineering-ready PRDs.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
