import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";
import Sidebar from "./components/Sidebar";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-poppins",
  display: "swap",
});

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
    <html lang="en" className={poppins.variable}>
      <body
        className="min-h-screen"
        style={{
          background: "var(--bg)",
          color: "var(--text-primary)",
          fontFamily: "var(--font-poppins), system-ui, sans-serif",
        }}
      >
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-x-hidden">
            <div className="max-w-7xl mx-auto px-6 py-6">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
