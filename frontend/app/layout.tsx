import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Content Automation",
  description: "Autonomous Indian Finance Content Pipeline",
};

const NAV_SECTIONS = [
  {
    label: "Main",
    links: [
      { href: "/orchestrator", text: "Orchestrator" },
      { href: "/", text: "Dashboard" },
      { href: "/ideas", text: "Gate 1 — Ideas" },
      { href: "/drafts", text: "Gate 2 — Drafts" },
    ],
  },
  {
    label: "Pipeline",
    links: [
      { href: "/tables/curated_sites", text: "Curated Sites" },
      { href: "/tables/raw_content", text: "Raw Content" },
      { href: "/tables/ideas", text: "Ideas (all)" },
      { href: "/tables/drafts", text: "Drafts (all)" },
      { href: "/tables/published_posts", text: "Published Posts" },
      { href: "/subscribers", text: "Subscribers" },
    ],
  },
  {
    label: "Analytics & Learning",
    links: [
      { href: "/tables/content_analytics", text: "Content Analytics" },
      { href: "/tables/style_guide", text: "Style Guide" },
      { href: "/tables/topic_performance_model", text: "Topic Model" },
    ],
  },
  {
    label: "Data Stores",
    links: [
      { href: "/tables/brand_memory", text: "Brand Memory" },
      { href: "/knowledge-base", text: "Knowledge Base" },
      { href: "/tables/email_subscribers", text: "Email Subscribers (raw)" },
      { href: "/tables/user_decision_summaries", text: "Decision Summaries" },
    ],
  },
  {
    label: "Ops",
    links: [
      { href: "/tables/run_logs", text: "Run Logs" },
      { href: "/tables/site_health_log", text: "Site Health" },
      { href: "/tables/cost_log", text: "Cost Log" },
    ],
  },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="w-56 bg-white border-r border-gray-200 flex-shrink-0 overflow-y-auto">
            <div className="px-4 py-4 border-b border-gray-100">
              <Link href="/" className="font-semibold text-gray-900 text-sm">
                Content Automation
              </Link>
            </div>
            <nav className="py-2">
              {NAV_SECTIONS.map((section) => (
                <div key={section.label} className="mb-1">
                  <div className="px-4 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    {section.label}
                  </div>
                  {section.links.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      className="block px-4 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                    >
                      {link.text}
                    </Link>
                  ))}
                </div>
              ))}
            </nav>
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-x-hidden">
            <div className="max-w-7xl mx-auto px-6 py-6">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
