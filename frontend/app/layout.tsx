import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Content Automation",
  description: "Autonomous Indian Finance Content Pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
          <span className="font-semibold text-gray-900 text-sm">
            Content Automation
          </span>
          <div className="flex gap-4">
            <Link href="/" className="text-sm text-gray-600 hover:text-gray-900">
              Dashboard
            </Link>
            <Link
              href="/ideas"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Gate 1 — Ideas
            </Link>
            <Link
              href="/drafts"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Gate 2 — Drafts
            </Link>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
