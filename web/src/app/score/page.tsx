"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

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

type SectionName = (typeof SOW_SECTIONS)[number];

type GuidanceItem = {
  role: "instruction" | "optional_language" | "placeholder";
  subheading: string | null;
  text: string;
  enclosing_text: string;
};

type TemplateSection = {
  name: string;
  title: string;
  guidance_count: number;
  guidance: GuidanceItem[];
};

type TemplateDoc = {
  id: string;
  engagement_type: string;
  display_name: string;
  source_file: string;
  section_count: number;
  sections: TemplateSection[];
};

const ROLE_COLOR: Record<GuidanceItem["role"], string> = {
  instruction: "#950095",
  optional_language: "#00873d",
  placeholder: "#d1242f",
};

const ROLE_LABEL: Record<GuidanceItem["role"], string> = {
  instruction: "Instruction (delete)",
  optional_language: "Suggested language",
  placeholder: "Placeholder (fill in)",
};

const CANONICAL_TITLES: Record<SectionName, string> = {
  background: "Background",
  objectives: "Objectives",
  scope: "Scope",
  out_of_scope: "Out of scope",
  approach: "Approach",
  deliverables: "Deliverables",
  assumptions: "Assumptions",
  roles_and_responsibilities: "Roles and responsibilities",
  schedule: "Schedule",
  fees_and_payment: "Fees and payment",
  terms: "Terms",
};

/** Fuzzy-pick guidance from the template doc for one canonical section. */
function pickGuidance(template: TemplateDoc | null, name: SectionName): GuidanceItem[] {
  if (!template) return [];
  const needles: Record<SectionName, string[]> = {
    background: ["background", "introduction", "overview"],
    objectives: ["objective"],
    scope: ["scope", "approach"],
    out_of_scope: ["out of scope", "out-of-scope"],
    approach: ["approach", "delivery"],
    deliverables: ["deliverable"],
    assumptions: ["assumption", "responsibilities"],
    roles_and_responsibilities: ["role", "responsibilities", "organization"],
    schedule: ["schedule", "timeline"],
    fees_and_payment: ["fee", "payment", "compensation"],
    terms: ["term", "compliance", "privacy", "security", "governance"],
  };
  const keys = needles[name];
  for (const sec of template.sections) {
    const t = (sec.title || "").toLowerCase();
    if (keys.some((k) => t.includes(k))) {
      return sec.guidance;
    }
  }
  return [];
}

function ScoreInner() {
  const search = useSearchParams();
  const templateId = search.get("template");

  const [template, setTemplate] = useState<TemplateDoc | null>(null);
  const [tplError, setTplError] = useState<string | null>(null);
  const [bodies, setBodies] = useState<Record<SectionName, string>>(() =>
    Object.fromEntries(SOW_SECTIONS.map((n) => [n, ""])) as Record<SectionName, string>,
  );
  const [activeSection, setActiveSection] = useState<SectionName>("background");
  const [result, setResult] = useState<string>("");
  const [status, setStatus] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!templateId) return;
    fetch(`/api/templates/${encodeURIComponent(templateId)}`)
      .then((r) => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then((j: TemplateDoc) => setTemplate(j))
      .catch((e) => setTplError(String(e)));
  }, [templateId]);

  const guidanceForActive = useMemo(
    () => pickGuidance(template, activeSection),
    [template, activeSection],
  );

  function buildBundle() {
    return {
      runId: "run-" + Math.random().toString(36).slice(2, 10),
      oppId: "opp-demo-001",
      corpusSnapshotId: "cs_4f53cda18c2baa0c0354bb5f",
      templateId: templateId || undefined,
      sow: {
        oppId: "opp-demo-001",
        templateProfile: templateId || "msd-v1",
        sections: SOW_SECTIONS.map((name) => ({
          name,
          title: CANONICAL_TITLES[name],
          body: bodies[name] || `(empty ${name})`,
        })),
      },
      be: { oppId: "opp-demo-001", currency: "USD", lineItems: [] },
      wbs: { oppId: "opp-demo-001", tasks: [] },
    };
  }

  async function submit() {
    setBusy(true);
    setResult("");
    setStatus(null);
    try {
      const res = await fetch("/api/score?layers=det,judges", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildBundle()),
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

  function insertGuidance(text: string) {
    setBodies((prev) => {
      const cur = prev[activeSection];
      const sep = cur && !cur.endsWith("\n") ? "\n" : "";
      return { ...prev, [activeSection]: cur + sep + text + "\n" };
    });
  }

  return (
    <main
      style={{
        padding: "1.5rem",
        maxWidth: 1280,
        margin: "0 auto",
        fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
        <h1 style={{ margin: 0 }}>Author SOW</h1>
        <Link href="/" style={{ fontSize: 14 }}>← change template</Link>
      </div>
      {templateId ? (
        <p style={{ marginTop: 4, color: "#57606a" }}>
          Template:{" "}
          <strong>
            {template ? template.display_name : tplError ? "(failed to load)" : "loading…"}
          </strong>
          {tplError && (
            <span style={{ color: "crimson", marginLeft: 8 }}>{tplError}</span>
          )}
        </p>
      ) : (
        <p style={{ color: "crimson" }}>
          No template selected. <Link href="/">Pick one →</Link>
        </p>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "200px 1fr 320px",
          gap: 16,
          marginTop: 16,
          alignItems: "start",
        }}
      >
        {/* Section list */}
        <nav
          style={{
            border: "1px solid #d0d7de",
            borderRadius: 8,
            background: "#f6f8fa",
            padding: 8,
          }}
        >
          {SOW_SECTIONS.map((n) => (
            <button
              key={n}
              onClick={() => setActiveSection(n)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "6px 8px",
                margin: "2px 0",
                border: "none",
                borderRadius: 4,
                background: n === activeSection ? "#0969da" : "transparent",
                color: n === activeSection ? "#fff" : "#24292f",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              {CANONICAL_TITLES[n]}
            </button>
          ))}
        </nav>

        {/* Editor */}
        <section>
          <h2 style={{ marginTop: 0 }}>{CANONICAL_TITLES[activeSection]}</h2>
          <textarea
            value={bodies[activeSection]}
            onChange={(e) =>
              setBodies({ ...bodies, [activeSection]: e.target.value })
            }
            spellCheck
            placeholder={`Author ${CANONICAL_TITLES[activeSection]} content…`}
            style={{
              width: "100%",
              minHeight: 360,
              padding: 12,
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              fontSize: 13,
              border: "1px solid #d0d7de",
              borderRadius: 6,
            }}
          />
          <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={submit} disabled={busy} style={{ padding: "8px 16px" }}>
              {busy ? "Scoring…" : "Score bundle"}
            </button>
            {status !== null && (
              <span style={{ color: status === 200 ? "green" : "crimson" }}>
                HTTP {status}
              </span>
            )}
          </div>
          <h3>Result</h3>
          <pre
            style={{
              background: "#0b0f14",
              color: "#d6deeb",
              padding: 12,
              minHeight: 120,
              overflow: "auto",
              fontSize: 12,
              borderRadius: 6,
            }}
          >
            {result || "(no response yet)"}
          </pre>
        </section>

        {/* Guidance rail */}
        <aside
          style={{
            border: "1px solid #d0d7de",
            borderRadius: 8,
            padding: 12,
            background: "#fff",
            maxHeight: "80vh",
            overflowY: "auto",
          }}
        >
          <h3 style={{ marginTop: 0, fontSize: 14 }}>Template guidance</h3>
          {!templateId && (
            <p style={{ fontSize: 13, color: "#57606a" }}>
              Choose a template to see authoring guidance.
            </p>
          )}
          {templateId && template && guidanceForActive.length === 0 && (
            <p style={{ fontSize: 13, color: "#57606a" }}>
              No guidance for this section in <code>{template.id}</code>.
            </p>
          )}
          {guidanceForActive.map((g, i) => (
            <div
              key={i}
              style={{
                borderLeft: `3px solid ${ROLE_COLOR[g.role]}`,
                padding: "6px 8px",
                margin: "8px 0",
                background: "#f6f8fa",
                borderRadius: 4,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: ROLE_COLOR[g.role],
                  textTransform: "uppercase",
                }}
              >
                {ROLE_LABEL[g.role]}
              </div>
              {g.subheading && (
                <div style={{ fontSize: 11, color: "#57606a", marginTop: 2 }}>
                  {g.subheading}
                </div>
              )}
              <div
                style={{
                  fontSize: 13,
                  marginTop: 4,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {g.text}
              </div>
              {g.role === "optional_language" && (
                <button
                  onClick={() => insertGuidance(g.text)}
                  style={{
                    marginTop: 6,
                    padding: "2px 8px",
                    fontSize: 12,
                    border: "1px solid #d0d7de",
                    borderRadius: 4,
                    background: "#fff",
                    cursor: "pointer",
                  }}
                >
                  Insert into section
                </button>
              )}
            </div>
          ))}
        </aside>
      </div>
    </main>
  );
}

export default function ScorePage() {
  return (
    <Suspense fallback={<main style={{ padding: "2rem" }}>Loading…</main>}>
      <ScoreInner />
    </Suspense>
  );
}
