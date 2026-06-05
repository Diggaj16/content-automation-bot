"use client";

import { use } from "react";
import TableBrowser from "../../components/TableBrowser";

const TABLE_TITLES: Record<string, string> = {
  curated_sites: "Curated Sites",
  raw_content: "Raw Content (Articles)",
  ideas: "Ideas",
  user_decision_summaries: "User Decision Summaries",
  drafts: "Drafts",
  published_posts: "Published Posts",
  content_analytics: "Content Analytics",
  email_subscribers: "Email Subscribers",
  style_guide: "Style Guide",
  topic_performance_model: "Topic Performance Model",
  brand_memory: "Brand Memory",
  knowledge_base: "Knowledge Base",
  run_logs: "Run Logs",
  site_health_log: "Site Health Log",
  cost_log: "Cost Log",
};

export default function TablePage({
  params,
}: {
  params: Promise<{ table: string }>;
}) {
  const { table } = use(params);
  const title = TABLE_TITLES[table] || table;

  return <TableBrowser tableName={table} title={title} />;
}
