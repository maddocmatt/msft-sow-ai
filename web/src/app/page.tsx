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
    <>
      <header className="app-header">
        <span className="brand">msft-sow-ai</span>
        <span className="crumb">Federal SOW authoring + SQA gatekeeper</span>
        <span className="spacer" />
        <Link className="btn" href="/score/">
          Raw scoring console
        </Link>
      </header>

      <main className="landing">
        <div className="landing-hero">
          <h1>Start a new Statement of Work</h1>
          <p>
            Pick the engagement type to load the right template. Each section panel
            shows the official authoring guidance pulled from the source .docx —
            instructions to delete, suggested language to keep, and placeholders to
            fill in.
          </p>
        </div>

        {error && (
          <div className="error-banner">Failed to load templates: {error}</div>
        )}
        {!templates && !error && (
          <p style={{ color: "var(--fg-muted)" }}>Loading…</p>
        )}
        {templates && templates.length === 0 && (
          <p style={{ color: "var(--fg-muted)" }}>No templates configured.</p>
        )}

        <div className="template-grid">
          {templates?.map((t) => (
            <Link
              key={t.id}
              href={`/score/?template=${encodeURIComponent(t.id)}`}
              className="template-card"
            >
              <span className="tag">{t.engagement_type}</span>
              <div className="name">{t.display_name}</div>
              {t.description && <div className="desc">{t.description}</div>}
              <div className="cta">Start authoring →</div>
            </Link>
          ))}
        </div>
      </main>
    </>
  );
}
