"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import GlobalJobMonitor from "./GlobalJobMonitor";

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

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");

  return (
    <aside className="w-56 bg-white border-r flex-shrink-0 overflow-y-auto flex flex-col" style={{ borderColor: "var(--border)" }}>
      <div className="px-4 py-4 border-b" style={{ borderColor: "var(--border)" }}>
        <Link href="/" className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
          Content Automation
        </Link>
      </div>

      <nav className="py-2 flex-1">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-1">
            <div
              className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: "var(--text-muted)" }}
            >
              {section.label}
            </div>
            {section.links.map((link) => {
              const active = isActive(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className="block px-4 py-1.5 text-sm transition-colors"
                  style={
                    active
                      ? {
                          color: "var(--brand-text)",
                          background: "var(--brand-soft)",
                          fontWeight: 500,
                        }
                      : { color: "var(--text-secondary)" }
                  }
                >
                  {link.text}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <GlobalJobMonitor />
    </aside>
  );
}
