import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "msft-sow-ai",
  description: "Federal SOW + BE + WBS drafter with deterministic SQA gatekeeper",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
