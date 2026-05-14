"use client";

import { useMemo, useState } from "react";

const SOW_SECTIONS = [
  "background",
  "objectives",
  "scope",
  "out_of_scope",
  "approach",
  "deliverables",
  "assumptions",
  "roles_and_responsibilities",
  "schedule",
  "fees_and_payment",
  "terms",
] as const;

function sampleBundle() {
  return {
    runId: "run-" + Math.random().toString(36).slice(2, 10),
    oppId: "opp-demo-001",
    corpusSnapshotId: "cs_4f53cda18c2baa0c0354bb5f",
    sow: {
      oppId: "opp-demo-001",
      templateProfile: "msd-v1",
      sections: SOW_SECTIONS.map((name) => ({
        name,
        title: name.replaceAll("_", " "),
        body: "Lorem ipsum body content for the " + name + " section.",
      })),
    },
    be: { oppId: "opp-demo-001", currency: "USD", lineItems: [] },
    wbs: { oppId: "opp-demo-001", tasks: [] },
  };
}

export default function ScorePage() {
  const initial = useMemo(() => JSON.stringify(sampleBundle(), null, 2), []);
  const [body, setBody] = useState(initial);
  const [result, setResult] = useState<string>("");
  const [status, setStatus] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setResult("");
    setStatus(null);
    try {
      const res = await fetch("/api/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      setStatus(res.status);
      const text = await res.text();
      try {
        setResult(JSON.stringify(JSON.parse(text), null, 2));
      } catch {
        setResult(text);
      }
    } catch (e) {
      setResult(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      style={{
        padding: "2rem",
        maxWidth: 960,
        margin: "0 auto",
        fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
      }}
    >
      <h1>Score</h1>
      <p>
        POSTs the artifact bundle below to <code>/api/score</code> (proxied to
        the Function App by SWA). The deterministic gatekeeper returns an{" "}
        <code>SqaReport</code>.
      </p>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        spellCheck={false}
        style={{
          width: "100%",
          minHeight: 320,
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 12,
          padding: 12,
        }}
      />
      <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
        <button onClick={submit} disabled={busy} style={{ padding: "8px 16px" }}>
          {busy ? "Scoring…" : "Score"}
        </button>
        {status !== null && (
          <span style={{ color: status === 200 ? "green" : "crimson" }}>
            HTTP {status}
          </span>
        )}
      </div>
      <h2>Result</h2>
      <pre
        style={{
          background: "#0b0f14",
          color: "#d6deeb",
          padding: 12,
          minHeight: 120,
          overflow: "auto",
          fontSize: 12,
        }}
      >
        {result || "(no response yet)"}
      </pre>
    </main>
  );
}
