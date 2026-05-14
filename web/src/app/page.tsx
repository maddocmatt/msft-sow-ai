"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type TemplateMeta = {
  id: string;
  engagement_type: string;
  display_name: string;
  description?: string | null;
};

export default function Home() {
  const [templates, setTemplates] = useState<TemplateMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/templates")
      .then((r) => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then((j) => setTemplates(j.templates ?? []))
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main
      style={{
        padding: "2rem",
        maxWidth: 960,
        margin: "0 auto",
        fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
      }}
    >
      <h1>msft-sow-ai</h1>
      <p>
        Federal SOW + Budgetary Estimate + WBS drafter, with a deterministic SQA
        gatekeeper. Pick the engagement type to start authoring.
      </p>
      <h2 style={{ marginTop: 32 }}>Choose a template</h2>
      {error && <p style={{ color: "crimson" }}>Failed to load templates: {error}</p>}
      {!templates && !error && <p>Loading…</p>}
      {templates && templates.length === 0 && <p>No templates configured.</p>}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 16,
          marginTop: 16,
        }}
      >
        {templates?.map((t) => (
          <Link
            key={t.id}
            href={`/score/?template=${encodeURIComponent(t.id)}`}
            style={{
              display: "block",
              border: "1px solid #d0d7de",
              borderRadius: 8,
              padding: 16,
              textDecoration: "none",
              color: "inherit",
              background: "#fff",
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "#57606a",
                textTransform: "uppercase",
              }}
            >
              {t.engagement_type}
            </div>
            <div style={{ fontWeight: 600, marginTop: 4 }}>{t.display_name}</div>
            {t.description && (
              <div style={{ fontSize: 13, color: "#57606a", marginTop: 8 }}>
                {t.description}
              </div>
            )}
            <div style={{ fontSize: 12, color: "#0969da", marginTop: 12 }}>
              Start authoring →
            </div>
          </Link>
        ))}
      </div>
      <p style={{ marginTop: 32, fontSize: 13, color: "#57606a" }}>
        Or <Link href="/score/">open the raw scoring console</Link> to paste a JSON
        bundle directly.
      </p>
    </main>
  );
}
