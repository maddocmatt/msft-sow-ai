"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { diffWords, type DiffSeg } from "../../lib/diff";

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

type Change = {
  before: string;
  after: string;
  rule: string;
  why: string;
};

type Phase = { name: string; ms: number };

type PolishResult = {
  rewritten: string;
  summary: string;
  changes: Change[];
  model: string;
  error?: string;
  phases?: Phase[];
};

const ROLE_LABEL: Record<Role, string> = {
  instruction: "Instruction (delete)",
  optional_language: "Suggested language",
  placeholder: "Placeholder (fill in)",
};

type EditableUnit = {
  // Stable id used as the dictionary key for body/result state
  id: string;
  sectionTitle: string;
  subheading: string | null;
  guidance: GuidanceItem[];
};

function buildUnits(template: TemplateDoc | null): EditableUnit[] {
  if (!template) return [];
  const units: EditableUnit[] = [];
  for (const sec of template.sections) {
    if (sec.name === "_unclassified") continue;
    // Group guidance items by subheading
    const bySub = new Map<string | null, GuidanceItem[]>();
    for (const g of sec.guidance) {
      const k = g.subheading || null;
      if (!bySub.has(k)) bySub.set(k, []);
      bySub.get(k)!.push(g);
    }
    if (bySub.size === 0) {
      units.push({
        id: `${sec.name}::_root`,
        sectionTitle: sec.title,
        subheading: null,
        guidance: [],
      });
      continue;
    }
    // Always include a section-level (no subheading) unit first if there are
    // section-level items or if there's only one subheading group.
    const subs = Array.from(bySub.keys());
    const hasRoot = subs.includes(null);
    if (hasRoot) {
      units.push({
        id: `${sec.name}::_root`,
        sectionTitle: sec.title,
        subheading: null,
        guidance: bySub.get(null) || [],
      });
    }
    for (const sub of subs) {
      if (sub === null) continue;
      units.push({
        id: `${sec.name}::${sub}`,
        sectionTitle: sec.title,
        subheading: sub,
        guidance: bySub.get(sub) || [],
      });
    }
  }
  return units;
}

function ScoreInner() {
  const search = useSearchParams();
  const templateId = search.get("template");

  const [template, setTemplate] = useState<TemplateDoc | null>(null);
  const [tplError, setTplError] = useState<string | null>(null);
  const [bodies, setBodies] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, PolishResult | null>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hoverChange, setHoverChange] = useState<number | null>(null);
  const [showCompile, setShowCompile] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  // Live polish status
  const [polishStartedAt, setPolishStartedAt] = useState<number | null>(null);
  const [livePhase, setLivePhase] = useState<string>("");
  const [elapsedMs, setElapsedMs] = useState(0);

  const storageKey = templateId ? `sowai:draft:${templateId}` : null;

  // Hydrate from localStorage once we know the templateId
  useEffect(() => {
    if (!storageKey) return;
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const j = JSON.parse(raw) as { bodies?: Record<string, string> };
        if (j.bodies) setBodies(j.bodies);
      }
    } catch {
      /* ignore */
    }
    setHydrated(true);
  }, [storageKey]);

  // Persist on every body change (after hydration)
  useEffect(() => {
    if (!storageKey || !hydrated) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify({ bodies }));
    } catch {
      /* ignore quota errors */
    }
  }, [bodies, storageKey, hydrated]);

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

  const units = useMemo(() => buildUnits(template), [template]);

  useEffect(() => {
    if (units.length > 0 && activeId === null) {
      setActiveId(units[0].id);
    }
  }, [units, activeId]);

  const active = useMemo(
    () => units.find((u) => u.id === activeId) || null,
    [units, activeId],
  );

  async function polish() {
    if (!active) return;
    setBusyId(active.id);
    setHoverChange(null);
    setPolishStartedAt(Date.now());
    setLivePhase("Loading rubric + template guidance…");
    setElapsedMs(0);
    try {
      const res = await fetch("/api/polish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          templateId,
          sectionTitle: active.sectionTitle,
          subheading: active.subheading,
          body: bodies[active.id] || "",
        }),
      });
      const text = await res.text();
      let parsed: PolishResult;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = {
          rewritten: bodies[active.id] || "",
          summary: "",
          changes: [],
          model: "?",
          error: text,
        };
      }
      setResults((prev) => ({ ...prev, [active.id]: parsed }));
    } catch (e) {
      setResults((prev) => ({
        ...prev,
        [active.id]: {
          rewritten: bodies[active.id] || "",
          summary: "",
          changes: [],
          model: "?",
          error: String(e),
        },
      }));
    } finally {
      setBusyId(null);
      setPolishStartedAt(null);
      setLivePhase("");
    }
  }

  // Tick the elapsed counter + advance the simulated phase label while waiting.
  // Server returns real phase timings on completion (rendered separately).
  useEffect(() => {
    if (!polishStartedAt) return;
    const phaseScript: { atMs: number; label: string }[] = [
      { atMs: 0, label: "Loading rubric + template guidance…" },
      { atMs: 400, label: "Assembling prompt with section guidance…" },
      { atMs: 900, label: "Calling gpt-4-1-mini for SOW voice rewrite…" },
      { atMs: 6000, label: "Model is still drafting — large section…" },
      { atMs: 12000, label: "Checking heuristics for missed violations…" },
      { atMs: 14000, label: "Force-rewrite retry pass running…" },
      { atMs: 22000, label: "Almost there — finalizing change records…" },
    ];
    const id = window.setInterval(() => {
      const e = Date.now() - polishStartedAt;
      setElapsedMs(e);
      let lbl = phaseScript[0].label;
      for (const p of phaseScript) {
        if (e >= p.atMs) lbl = p.label;
      }
      setLivePhase(lbl);
    }, 200);
    return () => window.clearInterval(id);
  }, [polishStartedAt]);

  function acceptRewrite() {
    if (!active) return;
    const r = results[active.id];
    if (!r) return;
    setBodies((prev) => ({ ...prev, [active.id]: r.rewritten }));
    setResults((prev) => ({ ...prev, [active.id]: null }));
    setHoverChange(null);
  }

  function discardRewrite() {
    if (!active) return;
    setResults((prev) => ({ ...prev, [active.id]: null }));
    setHoverChange(null);
  }

  function insertGuidance(text: string) {
    if (!active) return;
    setBodies((prev) => {
      const cur = prev[active.id] || "";
      const sep = cur && !cur.endsWith("\n") ? "\n" : "";
      return { ...prev, [active.id]: cur + sep + text + "\n" };
    });
  }

  const result = active ? results[active.id] : null;
  const body = active ? bodies[active.id] || "" : "";
  const diffSegs: DiffSeg[] = useMemo(
    () => (result ? diffWords(body, result.rewritten) : []),
    [result, body],
  );

  // Group units by section title for sidebar rendering
  const sidebarGroups = useMemo(() => {
    const map = new Map<string, EditableUnit[]>();
    for (const u of units) {
      if (!map.has(u.sectionTitle)) map.set(u.sectionTitle, []);
      map.get(u.sectionTitle)!.push(u);
    }
    return Array.from(map.entries());
  }, [units]);

  // Build compiled markdown SOW from current bodies
  const compiledMarkdown = useMemo(() => {
    if (!template) return "";
    const lines: string[] = [];
    lines.push(`# ${template.display_name}`);
    lines.push("");
    lines.push(`*Template: \`${template.id}\` · Engagement: ${template.engagement_type}*`);
    lines.push("");
    for (const [sectionTitle, sectionUnits] of sidebarGroups) {
      lines.push(`## ${sectionTitle}`);
      lines.push("");
      for (const u of sectionUnits) {
        const text = (bodies[u.id] || "").trim();
        if (u.subheading) {
          lines.push(`### ${u.subheading}`);
          lines.push("");
        }
        if (text) {
          lines.push(text);
        } else {
          lines.push("_(empty)_");
        }
        lines.push("");
      }
    }
    return lines.join("\n");
  }, [template, sidebarGroups, bodies]);

  function downloadMarkdown() {
    if (!template) return;
    const blob = new Blob([compiledMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${template.id}-draft.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(compiledMarkdown);
    } catch {
      /* ignore */
    }
  }

  function clearAllDrafts() {
    if (!storageKey) return;
    if (!confirm("Discard all drafts for this template?")) return;
    setBodies({});
    setResults({});
    try {
      localStorage.removeItem(storageKey);
    } catch {
      /* ignore */
    }
  }

  // Counters for compile header
  const filledUnitCount = units.filter((u) => (bodies[u.id] || "").trim().length > 0).length;

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
          className="btn"
          onClick={() => setShowCompile((v) => !v)}
          disabled={!template}
        >
          {showCompile ? "Back to editor" : "Compile SOW"}
        </button>
        {!showCompile && (
          <button
            className="btn btn-primary"
            onClick={polish}
            disabled={!active || busyId !== null || !body.trim()}
          >
            {busyId ? "Polishing…" : "Polish this section"}
          </button>
        )}
      </header>

      {tplError && <div className="error-banner">{tplError}</div>}

      {showCompile && template && (
        <main className="compile-view">
          <div className="compile-toolbar">
            <div>
              <h2>Compiled SOW preview</h2>
              <div className="compile-meta">
                {filledUnitCount}/{units.length} units drafted ·{" "}
                {compiledMarkdown.length.toLocaleString()} chars · stored locally
                in your browser
              </div>
            </div>
            <span className="spacer" />
            <button className="btn" onClick={clearAllDrafts}>
              Clear drafts
            </button>
            <button className="btn" onClick={copyMarkdown}>
              Copy markdown
            </button>
            <button className="btn btn-primary" onClick={downloadMarkdown}>
              Download .md
            </button>
          </div>
          <pre className="compile-md">{compiledMarkdown}</pre>
        </main>
      )}

      {!showCompile && (
        <div className="author-shell">
          {/* Left: section nav driven by template */}
          <nav className="section-nav">
          <h3>{template ? `${template.display_name}` : "Sections"}</h3>
          {sidebarGroups.map(([sectionTitle, sectionUnits]) => (
            <div key={sectionTitle} className="nav-group">
              <div className="nav-group-title">{sectionTitle}</div>
              {sectionUnits.map((u) => {
                const filled = (bodies[u.id] || "").trim().length > 0;
                const polished = results[u.id] != null;
                const label = u.subheading ?? "(section overview)";
                return (
                  <button
                    key={u.id}
                    onClick={() => {
                      setActiveId(u.id);
                      setHoverChange(null);
                    }}
                    className={
                      (u.id === activeId ? "active " : "") +
                      (filled ? "has-content " : "") +
                      (polished ? "has-polish" : "")
                    }
                  >
                    <span>{label}</span>
                    <span
                      className={
                        "pill" + (u.guidance.length === 0 ? " dot-empty" : "")
                      }
                    >
                      {u.guidance.length}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Center: editor + diff */}
        <div className="editor-pane">
          {!active && (
            <div className="empty" style={{ padding: 32 }}>
              {templateId ? "Loading template…" : "Pick a template from the home page."}
            </div>
          )}

          {active && (
            <>
              <div className="editor-header">
                <div>
                  <h2>{active.sectionTitle}</h2>
                  {active.subheading && (
                    <div style={{ color: "var(--fg-muted)", fontSize: 13 }}>
                      {active.subheading}
                    </div>
                  )}
                </div>
                {result && (
                  <span
                    className={
                      "status-pill " +
                      (result.error
                        ? "fail"
                        : result.changes.length === 0
                          ? "pass"
                          : "fail")
                    }
                  >
                    {result.error
                      ? "Polish error"
                      : result.changes.length === 0
                        ? "Already clean"
                        : `${result.changes.length} edit${
                            result.changes.length === 1 ? "" : "s"
                          }`}
                  </span>
                )}
              </div>

              <div className="editor-body">
                {busyId === active.id && (
                  <div className="polish-status" role="status" aria-live="polite">
                    <div className="polish-status-head">
                      <div className="spinner" aria-hidden="true" />
                      <div className="phase-timer">{(elapsedMs / 1000).toFixed(1)}s</div>
                    </div>
                    <div className="phase-label">{livePhase || "Working…"}</div>
                    <div className="phase-hint">
                      Polishing can take 10–25s for long sections — the model may also run a
                      second force-rewrite pass if the first attempt missed violations.
                    </div>
                  </div>
                )}

                {busyId !== active.id && !result && (
                  <textarea
                    value={body}
                    onChange={(e) =>
                      setBodies({ ...bodies, [active.id]: e.target.value })
                    }
                    spellCheck
                    placeholder={`Draft the "${
                      active.subheading ?? active.sectionTitle
                    }" content. Use the template guidance on the right, then click "Polish this section" to apply Microsoft Federal SOW voice.`}
                  />
                )}

                {result && busyId !== active.id && (
                  <div className="diff-view">
                    <div className="diff-summary">
                      <strong>{result.summary || "Polish complete"}</strong>
                      <span className="model-tag">model: {result.model}</span>
                    </div>

                    {result.phases && result.phases.length > 0 && (
                      <div className="phase-timeline">
                        {result.phases.map((p, i) => (
                          <div key={i} className="phase-chip">
                            <span className="phase-chip-name">{p.name}</span>
                            <span className="phase-chip-ms">{p.ms} ms</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {result.error && (
                      <pre className="diff-error">{result.error}</pre>
                    )}

                    <div className="diff-grid">
                      <div className="diff-col">
                        <div className="diff-col-title">Original</div>
                        <div className="diff-text">
                          {diffSegs.map((s, i) =>
                            s.type === "ins" ? null : (
                              <span
                                key={i}
                                className={s.type === "del" ? "del" : "eq"}
                              >
                                {s.text}
                              </span>
                            ),
                          )}
                        </div>
                      </div>
                      <div className="diff-col">
                        <div className="diff-col-title">Polished</div>
                        <div className="diff-text">
                          {diffSegs.map((s, i) =>
                            s.type === "del" ? null : (
                              <span
                                key={i}
                                className={s.type === "ins" ? "ins" : "eq"}
                              >
                                {s.text}
                              </span>
                            ),
                          )}
                        </div>
                      </div>
                    </div>

                    {result.changes.length > 0 && (
                      <div className="changes-list">
                        <h4>Why these edits</h4>
                        {result.changes.map((c, i) => (
                          <div
                            key={i}
                            className={
                              "change-row " + (hoverChange === i ? "active" : "")
                            }
                            onMouseEnter={() => setHoverChange(i)}
                            onMouseLeave={() => setHoverChange(null)}
                          >
                            <span className="change-rule">{c.rule}</span>
                            <div className="change-pair">
                              <div className="change-before">
                                <span className="lbl">before</span> {c.before}
                              </div>
                              <div className="change-after">
                                <span className="lbl">after</span> {c.after}
                              </div>
                            </div>
                            <div className="change-why">{c.why}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="diff-actions">
                      <button className="btn" onClick={discardRewrite}>
                        Keep my draft
                      </button>
                      <button
                        className="btn btn-primary"
                        onClick={acceptRewrite}
                        disabled={!!result.error}
                      >
                        Accept polished version
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Right: per-unit guidance rail */}
        <aside className="guidance-rail">
          <div className="rail-header">
            <h3>Template guidance</h3>
            <span className="count">
              {active ? active.guidance.length : 0}
            </span>
          </div>
          {!active && (
            <p style={{ fontSize: 13, color: "var(--fg-muted)" }}>
              Select a section to see its template-specific guidance.
            </p>
          )}
          {active && active.guidance.length === 0 && (
            <p style={{ fontSize: 13, color: "var(--fg-muted)" }}>
              No color-coded guidance was extracted for this unit. Draft freely;
              the polish pass still enforces SOW voice rules.
            </p>
          )}
          {active &&
            active.guidance.map((g, i) => (
              <div className={"guidance-card " + g.role} key={i}>
                <div className="role-label">{ROLE_LABEL[g.role]}</div>
                <div className="text">{g.text}</div>
                {g.role === "optional_language" && (
                  <div className="actions">
                    <button onClick={() => insertGuidance(g.text)}>
                      Insert into draft
                    </button>
                  </div>
                )}
              </div>
            ))}
        </aside>
      </div>
      )}
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
