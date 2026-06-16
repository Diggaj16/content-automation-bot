"use client";

import React, { useState } from "react";
import type { SourceArticle } from "../lib/api";

/**
 * Displays the scraped source article behind an idea or draft:
 * title, source, URL, structured summary, and the full scraped text.
 * Shared by Gate 1 (Ideas) and Gate 2 (Drafts).
 */
const SourceArticlePanel = React.memo(function SourceArticlePanel({ article }: { article: SourceArticle }) {
  const [showFull, setShowFull] = useState(false);
  const summary = article.structured_summary;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-gray-900 text-sm">{article.title}</div>
        <span className="text-gray-400 whitespace-nowrap text-[10px]">{article.word_count} words</span>
      </div>

      <div className="flex items-center gap-2 text-gray-500 flex-wrap">
        <span>{article.source_name}</span>
        <span>|</span>
        <a href={article.url} target="_blank" rel="noopener noreferrer"
           className="text-blue-600 hover:underline truncate max-w-md">
          {article.url}
        </a>
        {article.pre_score != null && (
          <><span>|</span><span>Pre-score: {article.pre_score.toFixed(1)}</span></>
        )}
        {article.vision_fallback_used && (
          <span className="bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded">Vision fallback</span>
        )}
        {article.paywall_detected && (
          <span className="bg-red-100 text-red-600 px-1.5 py-0.5 rounded">Paywall detected</span>
        )}
      </div>

      {summary && (
        <div className="space-y-1.5 pt-1 border-t border-gray-200">
          <div><span className="font-semibold text-gray-700">Story: </span><span className="text-gray-600">{summary.story_narrative}</span></div>
          {summary.key_data_points.length > 0 && (
            <div><span className="font-semibold text-gray-700">Key data: </span><span className="text-gray-600">{summary.key_data_points.join(" | ")}</span></div>
          )}
          {summary.mechanism && (
            <div><span className="font-semibold text-gray-700">Mechanism: </span><span className="text-gray-600">{summary.mechanism}</span></div>
          )}
          {summary.implications && (
            <div><span className="font-semibold text-gray-700">Implications: </span><span className="text-gray-600">{summary.implications}</span></div>
          )}
        </div>
      )}

      <div>
        <button onClick={() => setShowFull((v) => !v)} className="text-blue-600 hover:underline text-xs">
          {showFull ? "Hide scraped text" : "Show full scraped text"}
        </button>
        {showFull && (
          <pre className="mt-2 bg-white border border-gray-200 rounded p-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-gray-700 leading-relaxed">
            {article.full_text}
          </pre>
        )}
      </div>
    </div>
  );
});

export default SourceArticlePanel;
