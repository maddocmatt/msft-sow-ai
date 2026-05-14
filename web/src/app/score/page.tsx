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
type Role = "instruction" | "optional_language" | "placeholder";

type GuidanceItem = {
  role: Role;
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

type Finding = {
  ruleId: string;
  severity: "blocker" | "major" | "minor";
  artifact: string;
  locator: string;
  description: string;
  remediationHint?: string | null;
};

type Report = {
  passed: boolean;
  findings: Finding[];
  rubricVersion: string;
};

const ROLE_LABEL: Record<Role, string> = {
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

const SECTION_NEEDLES: Record<SectionName, string[]> = {
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

function pickGuidance(template: TemplateDoc | null, name: SectionName): GuidanceItem[] {
  if (!template) return [];
  const keys = SECTION_NEEDLES[name];
  for (const sec of template.sections) {
    const t = (sec.title || "").toLowerCase();
    if (keys.some((k) => t.includes(k))) return sec.guidance;
  }
  return [];
}

function wordCount(s: string): number {
  return s.trim().split(/\s+/).filter(Boolean).length;
}

function ScoreInner() {
  const search = useSearchParams();
  const templateId = search.get("template");

  const [template, setTemplate] = useState<TemplateDoc | null>(null);
  const [tplError, setTplError] = useState<string | null>(null);
  const [bodies, setBodies] = useState<Record<SectionName, string>>(
    () =>
      Object.fromEntries(SOW_SECTIONS.map((n) => [n, ""])) as Record<
        SectionName,
        string
      >,
  );
  const [activeSection, setActiveSection] = useState<SectionName>("background");
  const [report, setReport] = useState<Report | null>(null);
  const [rawError, setRawError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const [roleFilters, setRoleFilters] = useState<Record<Role, boolean>>({
    instruction: true,
    optional_language: true,
    placeholder: true,
  });

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

  const guidance = useMemo(
    () => pickGuidance(template, activeSection),
    [template, activeSection],
  );
  const filteredGuidance = useMemo(
    () => guidance.filter((g) => roleFilters[g.role]),
    [guidance, roleFilters],
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
    setReport(null);
    setRawError(null);
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
        const parsed = JSON.parse(text);
        if (typeof parsed?.passed === "boolean") {
          setReport(parsed as Report);
        } else {
          setRawError(text);
        }
      } catch {
        setRawError(text);
      }
    } catch (e) {
      setRawError(String(e));
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

  const totalFindings = report?.findings.length ?? 0;
  const blockers = report?.findings.filter((f) => f.severity === "blocker").length ?? 0;

  return (
    <>
      <header className="app-header">
        <Link href="/" className="brand" style={{ color: "var(--fg)" }}>
          msft-sow-ai
        </Link>
        <span className="crumb">
          {templateId ? (
            <>
              Template:{" "}
              <strong>
                {template
                  ? template.display_name
                  : tplError
                    ? "(failed to load)"
                    : "loading…"}
              </strong>
            </>
          ) : (
            <span style={{ color: "var(--danger)" }}>No template selected</span>
          )}
        </span>
        <span className="spacer" />
        <Link className="btn" href="/">
          ← Change template
        </Link>
        <button
          className="btn btn-primary"
          onClick={submit}
          disabled={busy || !templateId}
        >
          {busy ? "Scoring…" : "Score bundle"}
        </button>
      </header>

      {tplError && <div className="error-banner">{tplError}</div>}

      <div className="author-shell">
        {/* Left: section nav */}
        <nav className="section-nav">
          <h3>Sections</h3>
          {SOW_SECTIONS.map((n) => {
            const filled = bodies[n].trim().length > 0;
            const count = pickGuidance(template, n).length;
            return (
              <button
                key={n}
                onClick={() => setActiveSection(n)}
                className={
                  (n === activeSection ? "active " : "") +
                  (filled ? "has-content" : "")
                }
              >
                <span>{CANONICAL_TITLES[n]}</span>
                <span className={"pill" + (count === 0 ? " dot-empty" : "")}>
                  {count}
                </span>
              </button>
            );
          })}
        </nav>

        {/* Center: editor + result */}
        <div className="editor-pane">
          <div className="editor-header">
            <div>
              <h2>{CANONICAL_TITLES[activeSection]}</h2>
              <div className="word-count">
                {wordCount(bodies[activeSection])} words
                {guidance.length > 0 && ` · ${guidance.length} guidance items available`}
              </div>
            </div>
            {status !== null && (
              <span
                className={
                  "status-pill " +
                  (status === 200
                    ? report?.passed
                      ? "pass"
                      : "fail"
                    : "fail")
                }
              >
                HTTP {status}
                {report &&
                  ` · ${report.passed ? "Passed" : "Blocked"} · ${totalFindings} finding${
                    totalFindings === 1 ? "" : "s"
                  }`}
              </span>
            )}
          </div>

          <div className="editor-body">
            <textarea
              value={bodies[activeSection]}
              onChange={(e) =>
                setBodies({ ...bodies, [activeSection]: e.target.value })
              }
              spellCheck
              placeholder={`Author the ${CANONICAL_TITLES[activeSection].toLowerCase()} section here. Click "Insert" on a suggested language card on the right to drop it in.`}
            />

            {(report || rawError) && (
              <div className="result-panel">
                <div className="result-header">
                  <h3>SQA result</h3>
                  {report && (
                    <span
                      className={"status-pill " + (report.passed ? "pass" : "fail")}
                    >
                      {report.passed ? "Passed" : `Blocked (${blockers})`}
                    </span>
                  )}
                  {report && (
                    <span style={{ color: "var(--fg-subtle)", fontSize: 12 }}>
                      rubric {report.rubricVersion}
                    </span>
                  )}
                </div>

                {rawError && (
                  <pre style={{ padding: 16, overflow: "auto", fontSize: 12 }}>
                    {rawError}
                  </pre>
                )}

                {report && report.findings.length === 0 && (
                  <div className="empty">No findings — clean run.</div>
                )}

                {report && report.findings.length > 0 && (
                  <div className="findings-list">
                    {report.findings.map((f, i) => (
                      <div className="finding" key={i}>
                        <span className={"severity " + f.severity}>{f.severity}</span>
                        <div className="body">
                          <span className="rule-id">{f.ruleId}</span>
                          <span className="desc">{f.description}</span>
                          <span className="locator">
                            {f.artifact}:{f.locator}
                          </span>
                          {f.remediationHint && (
                            <span
                              style={{
                                fontSize: 12,
                                color: "var(--fg-muted)",
                                marginTop: 2,
                              }}
                            >
                              💡 {f.remediationHint}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: guidance rail */}
        <aside className="guidance-rail">
          <div className="rail-header">
            <h3>Template guidance</h3>
            <span className="count">
              {filteredGuidance.length}/{guidance.length}
            </span>
          </div>

          {guidance.length > 0 && (
            <div className="role-filters">
              {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
                <button
                  key={r}
                  className={"role-filter " + r + (roleFilters[r] ? " active" : "")}
                  onClick={() =>
                    setRoleFilters({ ...roleFilters, [r]: !roleFilters[r] })
                  }
                >
                  {r === "instruction"
                    ? "Instr"
                    : r === "optional_language"
                      ? "Suggest"
                      : "Slot"}
                </button>
              ))}
            </div>
          )}

          {!templateId && (
            <p style={{ fontSize: 13, color: "var(--fg-muted)" }}>
              Choose a template from the home page to see authoring guidance.
            </p>
          )}
          {templateId && template && guidance.length === 0 && (
            <p style={{ fontSize: 13, color: "var(--fg-muted)" }}>
              No guidance for <strong>{CANONICAL_TITLES[activeSection]}</strong> in{" "}
              <code>{template.id}</code>. The template may not have a matching
              section, or the section had no color-coded content.
            </p>
          )}
          {filteredGuidance.map((g, i) => (
            <div className={"guidance-card " + g.role} key={i}>
              <div className="role-label">{ROLE_LABEL[g.role]}</div>
              {g.subheading && <div className="subhead">{g.subheading}</div>}
              <div className="text">{g.text}</div>
              {g.role === "optional_language" && (
                <div className="actions">
                  <button onClick={() => insertGuidance(g.text)}>
                    Insert into section
                  </button>
                </div>
              )}
            </div>
          ))}
        </aside>
      </div>
    </>
  );
}

export default function ScorePage() {
  return (
    <Suspense
      fallback={
        <main style={{ padding: "2rem", color: "var(--fg-muted)" }}>Loading…</main>
      }
    >
      <ScoreInner />
    </Suspense>
  );
}
