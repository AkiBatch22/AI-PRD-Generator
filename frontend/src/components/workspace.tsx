"use client";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Sparkles,
  FileText,
  ShieldCheck,
  BookOpen,
  Download,
  Pencil,
  X,
  Plus,
} from "lucide-react";
import {
  PRD,
  Requirement,
  Brief,
  Question,
  Assumption,
  label,
  Status,
} from "@/lib/types";
import { api } from "@/lib/api";
import { Badge, Field, Modal, Spinner, StructuredValue, Empty } from "./ui";

const steps = [
  "draft",
  "discovery",
  "brief_review",
  "requirements",
  "review",
  "final",
];
export function Workspace({
  initial,
  onBack,
  onChange,
}: {
  initial: PRD;
  onBack: () => void;
  onChange: (p: PRD) => void;
}) {
  const [prd, setPrd] = useState(initial);
  const [tab, setTab] = useState("copilot");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [req, setReq] = useState<Requirement | null>(null);
  const [briefEdit, setBriefEdit] = useState(false);
  const [assumption, setAssumption] = useState<Assumption | null>(null);
  const [fix, setFix] = useState<{ id: string; text: string } | null>(null);
  const update = (p: PRD) => {
    setPrd(p);
    onChange(p);
  };
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      const p = await api<PRD>(`/prds/${prd.id}`);
      update(p);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const action = (path: string) =>
    run(() => api(`/prds/${prd.id}/${path}`, "POST"));
  const changeAssumption = (a: Assumption, status: Status) =>
    run(() => api(`/prds/${prd.id}/assumptions/${a.id}`, "PATCH", { status }));
  return (
    <div className="prd-workspace">
      <div className="prd-header">
        <button
          className="icon-button"
          aria-label="Back to workspace"
          onClick={onBack}
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1>{prd.title}</h1>
        </div>
        <Badge value={prd.status} />
        <div className="header-actions">
          <button className="secondary" onClick={() => setShowContext(true)}>
            <BookOpen size={15} />
            View context
          </button>
          <a
            className="secondary"
            href={`/api/prds/${prd.id}/export`}
            download={`${prd.title}.md`}
          >
            <Download size={15} />
            Export
          </a>
        </div>
      </div>
      {error && (
        <div role="alert" className="error-banner">
          {error}
          <button
            className="icon-button"
            onClick={() => setError("")}
            aria-label="Dismiss error"
          >
            <X size={16} />
          </button>
        </div>
      )}
      <div className="workspace-progress">
        Step {steps.indexOf(prd.status) + 1} of {steps.length} ·{" "}
        {label(prd.status)}
      </div>
      <nav className="editor-tabs" aria-label="PRD views">
        {(["copilot", "assumptions", "preview", "quality"] as const).map(
          (view) => (
            <button
              key={view}
              className={tab === view ? "active" : ""}
              aria-current={tab === view ? "page" : undefined}
              onClick={() => setTab(view)}
            >
              {view === "copilot" ? "Workflow" : label(view)}
            </button>
          ),
        )}
      </nav>
      <div className="editor-body">
        {tab !== "preview" && (
          <section className="copilot-panel">
            <div className="panel-title">
              <span className="spark-small">
                <Sparkles size={17} />
              </span>
              <strong>
                {tab === "copilot"
                  ? "Product copilot"
                  : tab === "assumptions"
                    ? "Assumptions ledger"
                    : "Quality report"}
              </strong>
              {busy && <Spinner />}
            </div>
            <div className="copilot-content">
              {tab === "copilot" && (
                <>
                  {prd.status === "draft" && (
                    <>
                      <div className="copilot-intro">
                        <h2>Let’s clarify the idea.</h2>
                        <p>
                          Before writing requirements, we’ll identify decisions
                          that your organization context doesn’t answer yet.
                        </p>
                      </div>
                      <div className="idea-card">
                        <span className="eyebrow">YOUR IDEA</span>
                        <p>{prd.idea}</p>
                      </div>
                      <div className="notice">
                        {prd.ai_relevant
                          ? "AI behavior, explainability, and fallback requirements will be included."
                          : "This initiative is configured without AI-specific requirements."}
                      </div>
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() => action("discovery")}
                      >
                        <Sparkles size={16} />
                        Start discovery
                      </button>
                    </>
                  )}
                  {prd.status === "discovery" && (
                    <>
                      <div className="copilot-intro">
                        <h2>A few questions that matter.</h2>
                        <p>
                          Answer what you know. Explicitly leave the rest
                          unresolved.
                        </p>
                      </div>
                      {prd.questions.map((q, i) => (
                        <QuestionCard
                          key={q.id}
                          question={q}
                          index={i}
                          busy={busy}
                          onSave={(answer, status) =>
                            run(() =>
                              api(
                                `/prds/${prd.id}/discovery/${q.id}`,
                                "PATCH",
                                { answer, status },
                              ),
                            )
                          }
                        />
                      ))}
                      <button
                        className="primary full"
                        disabled={
                          busy ||
                          prd.questions.some((q) => q.status === "unanswered")
                        }
                        onClick={() => action("brief")}
                      >
                        Generate product brief
                        <ArrowRight size={16} />
                      </button>
                    </>
                  )}
                  {prd.status === "brief_review" && prd.brief && (
                    <>
                      <div className="copilot-intro">
                        <h2>A shared understanding, before a specification.</h2>
                        <p>
                          Review the brief and its open questions. Approval
                          preserves uncertainty; it doesn’t confirm assumptions.
                        </p>
                      </div>
                      <button
                        className="secondary"
                        onClick={() => setBriefEdit(true)}
                      >
                        <Pencil size={15} />
                        Edit brief
                      </button>
                      <div className="brief-content">
                        {Object.entries(prd.brief.content).map(
                          ([key, value]) => (
                            <section key={key}>
                              <h3>{label(key)}</h3>
                              <StructuredValue value={value} />
                            </section>
                          ),
                        )}
                      </div>
                      <button
                        disabled={busy}
                        className="primary full"
                        onClick={() => action("brief/approve")}
                      >
                        <Check size={16} />
                        Approve brief & continue
                      </button>
                    </>
                  )}
                  {prd.status === "requirements" && (
                    <>
                      <div className="copilot-intro">
                        <h2>Make the plan testable.</h2>
                        <p>
                          Requirements are individual records with acceptance
                          criteria, dependencies, and edge cases.
                        </p>
                      </div>
                      {!prd.requirements.length ? (
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() => action("requirements")}
                        >
                          <Sparkles size={16} />
                          Generate requirements
                        </button>
                      ) : (
                        <>
                          <RequirementList
                            requirements={prd.requirements}
                            onEdit={setReq}
                          />
                          <button
                            className="secondary"
                            onClick={() =>
                              setReq({
                                id: "",
                                requirement_code: `FR-${String(prd.requirements.length + 1).padStart(2, "0")}`,
                                title: "",
                                description: "",
                                type: "functional",
                                priority: "must",
                                acceptance_criteria: [""],
                                dependencies: [],
                                edge_cases: [],
                              })
                            }
                          >
                            <Plus size={15} />
                            Add requirement
                          </button>
                          <p className="notice">
                            Review the assumptions ledger before assembling your
                            PRD. Unresolved decisions remain visible.
                          </p>
                          <button
                            className="primary full"
                            disabled={busy}
                            onClick={() => action("generate")}
                          >
                            Generate PRD
                            <ArrowRight size={16} />
                          </button>
                        </>
                      )}
                    </>
                  )}
                  {(prd.status === "review" || prd.status === "final") && (
                    <>
                      <div className="copilot-intro">
                        <h2>
                          {prd.status === "final"
                            ? "Ready for your team."
                            : "Give the draft a second look."}
                        </h2>
                        <p>
                          {prd.status === "final"
                            ? "Your reviewed document is finalized. Export it as Markdown for handoff."
                            : "The critic checks requirements, uncertainty, failure states, and organization rules."}
                        </p>
                      </div>
                      {prd.status === "review" && (
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() => action("review")}
                        >
                          <ShieldCheck size={16} />
                          Run PRD critic
                        </button>
                      )}
                      {prd.review_issues.length > 0 && (
                        <div className="review-list">
                          {prd.review_issues.map((i) => (
                            <article
                              className={`issue-card ${i.status !== "open" ? "faded" : ""}`}
                              key={i.id}
                            >
                              <div className="card-top">
                                <Badge value={i.severity} />
                                <Badge value={i.status} />
                              </div>
                              <h3>{i.title}</h3>
                              <p>
                                {i.description !== i.title
                                  ? i.description
                                  : `Affected section: ${label(i.affected_section)}`}
                              </p>
                              {i.current_text && (
                                <blockquote>{i.current_text}</blockquote>
                              )}
                              {i.suggested_change && (
                                <div className="notice">
                                  Suggested: {i.suggested_change}
                                </div>
                              )}
                              {i.status === "open" &&
                                prd.status !== "final" && (
                                  <div className="actions wrap">
                                    {i.suggested_change && i.current_text && (
                                      <button
                                        className="text-button"
                                        disabled={busy}
                                        onClick={() =>
                                          run(() =>
                                            api(
                                              `/prds/${prd.id}/review/${i.id}`,
                                              "PATCH",
                                              { action: "accept" },
                                            ),
                                          )
                                        }
                                      >
                                        Accept fix
                                      </button>
                                    )}
                                    {i.current_text &&
                                      !["assumptions", "requirements"].includes(
                                        i.affected_section,
                                      ) && (
                                        <button
                                          className="text-button"
                                          onClick={() =>
                                            setFix({
                                              id: i.id,
                                              text:
                                                i.suggested_change ||
                                                i.current_text,
                                            })
                                          }
                                        >
                                          Edit
                                        </button>
                                      )}
                                    {i.severity !== "critical" && (
                                      <button
                                        className="text-button muted"
                                        disabled={busy}
                                        onClick={() =>
                                          run(() =>
                                            api(
                                              `/prds/${prd.id}/review/${i.id}`,
                                              "PATCH",
                                              { action: "ignore" },
                                            ),
                                          )
                                        }
                                      >
                                        Acknowledge & ignore
                                      </button>
                                    )}
                                  </div>
                                )}
                            </article>
                          ))}
                        </div>
                      )}
                      {prd.status === "review" && (
                        <>
                          <details>
                            <summary>
                              Edit requirements to resolve issues
                            </summary>
                            <RequirementList
                              requirements={prd.requirements}
                              onEdit={setReq}
                            />
                          </details>
                          <p className="muted">
                            Finalization requires a fresh review and no open
                            issues. Critical issues cannot be ignored.
                          </p>
                          <button
                            className="primary full"
                            disabled={
                              busy ||
                              !prd.sections._reviewed ||
                              prd.review_issues.some((i) => i.status === "open")
                            }
                            onClick={() => action("finalize")}
                          >
                            <Check size={16} />
                            Finalize PRD
                          </button>
                        </>
                      )}
                    </>
                  )}
                </>
              )}
              {tab === "assumptions" && (
                <>
                  <p className="muted">
                    Confirm, challenge, or leave a decision unresolved. Only
                    confirmed assumptions can become organization knowledge.
                  </p>
                  {(
                    ["confirmed", "assumed", "unknown", "rejected"] as Status[]
                  ).map((status) => (
                    <section className="ledger-group" key={status}>
                      <div className="section-title">
                        <h3>
                          {status === "assumed"
                            ? "AI assumptions"
                            : label(status)}
                        </h3>
                        <span>
                          {
                            prd.assumptions.filter((a) => a.status === status)
                              .length
                          }
                        </span>
                      </div>
                      {prd.assumptions
                        .filter((a) => a.status === status)
                        .map((a) => (
                          <article className="assumption-card" key={a.id}>
                            <h3>{a.title}</h3>
                            <p>{a.content}</p>
                            {prd.status !== "final" &&
                              !a.promoted_context_id && (
                                <div className="actions wrap">
                                  {a.status !== "confirmed" && (
                                    <button
                                      disabled={busy}
                                      className="text-button"
                                      onClick={() =>
                                        changeAssumption(a, "confirmed")
                                      }
                                    >
                                      <Check size={14} />
                                      Confirm
                                    </button>
                                  )}
                                  <button
                                    className="text-button"
                                    onClick={() => setAssumption(a)}
                                  >
                                    <Pencil size={14} />
                                    Edit
                                  </button>
                                  {a.status !== "rejected" && (
                                    <button
                                      disabled={busy}
                                      className="text-button muted"
                                      onClick={() =>
                                        changeAssumption(a, "rejected")
                                      }
                                    >
                                      Reject
                                    </button>
                                  )}
                                  {a.status === "confirmed" && (
                                    <button
                                      disabled={busy}
                                      className="text-button"
                                      onClick={() =>
                                        run(() =>
                                          api(
                                            `/prds/${prd.id}/assumptions/${a.id}/promote`,
                                            "POST",
                                          ),
                                        )
                                      }
                                    >
                                      Add to organization context
                                    </button>
                                  )}
                                </div>
                              )}
                            {a.promoted_context_id && (
                              <span className="badge confirmed">
                                Added to organization context
                              </span>
                            )}
                          </article>
                        ))}
                    </section>
                  ))}
                  {!prd.assumptions.length && (
                    <Empty title="No assumptions yet">
                      The ledger will populate after the product brief is
                      generated.
                    </Empty>
                  )}
                </>
              )}
              {tab === "quality" && (
                <>
                  <div className="quality-hero">
                    <strong>
                      {prd.quality.overall}
                      <small>/100</small>
                    </strong>
                    <p>Deterministic quality score</p>
                  </div>
                  {Object.entries(prd.quality.breakdown).map(([key, value]) => (
                    <div className="quality-line" key={key}>
                      <div>
                        <span>{label(key)}</span>
                        <strong>{value}</strong>
                      </div>
                      <div className="progress">
                        <i style={{ width: `${value}%` }} />
                      </div>
                    </div>
                  ))}
                  <p className="notice">
                    Scores reflect completeness and explicit checks, not a
                    guarantee of product correctness. {prd.quality.issues}{" "}
                    review issues remain open.
                  </p>
                </>
              )}
            </div>
          </section>
        )}
        {tab === "preview" && (
          <section className="preview-panel">
            <div className="panel-title">
              <FileText size={16} />
              <strong>PRD preview</strong>
            </div>
            <div className="preview-paper">
              <div className="eyebrow">PRODUCT REQUIREMENTS</div>
              <h2>{prd.title}</h2>
              <Badge value={prd.status} />
              {prd.status === "draft" && (
                <>
                  <h3>Initiative</h3>
                  <p>{prd.idea}</p>
                  <div className="preview-placeholder">
                    Your specification takes shape as you work through
                    discovery.
                  </div>
                </>
              )}
              {prd.status === "discovery" && (
                <>
                  {prd.questions.map((q) => (
                    <section key={q.id}>
                      <h3>{label(q.category)}</h3>
                      <p>{q.answer || "Unresolved — awaiting discovery"}</p>
                    </section>
                  ))}
                </>
              )}
              {Object.entries(
                Object.keys(prd.document_sections).length
                  ? prd.document_sections
                  : prd.brief?.content || {},
              )
                .filter(([k]) => !k.startsWith("_") && k !== "assumptions")
                .map(([key, value]) => (
                  <section key={key}>
                    <h3>{label(key)}</h3>
                    <StructuredValue value={value} />
                  </section>
                ))}
              {prd.requirements.length > 0 &&
                !Object.keys(prd.document_sections).length && (
                  <section>
                    <h3>Requirements</h3>
                    {prd.requirements.map((r) => (
                      <div className="preview-requirement" key={r.id}>
                        <strong>
                          {r.requirement_code} · {r.title}
                        </strong>
                        <p>{r.description}</p>
                        <ul>
                          {r.acceptance_criteria.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                        <small>
                          Edge cases:{" "}
                          {r.edge_cases.join("; ") || "Not yet defined"}
                        </small>
                      </div>
                    ))}
                  </section>
                )}
              {prd.assumptions.length > 0 && (
                <section>
                  <h3>Assumptions & unresolved decisions</h3>
                  {prd.assumptions
                    .filter((a) => a.status !== "rejected")
                    .map((a) => (
                      <div className="preview-assumption" key={a.id}>
                        <Badge value={a.status} />
                        <p>{a.content}</p>
                      </div>
                    ))}
                </section>
              )}
            </div>
          </section>
        )}
      </div>
      {showContext && (
        <Modal
          title="Context supplied to this PRD"
          onClose={() => setShowContext(false)}
        >
          <div className="modal-body">
            <p className="notice">
              This is the exact context snapshot captured when the PRD was
              created. The critic also checks the latest organization rules.
            </p>
            <StructuredValue value={prd.context_snapshot} />
          </div>
        </Modal>
      )}
      {req && (
        <RequirementEditor
          value={req}
          busy={busy}
          error={error}
          onClose={() => setReq(null)}
          onSave={(data) =>
            run(async () => {
              await api(
                `/prds/${prd.id}/requirements/${req.id || "manual"}`,
                req.id ? "PUT" : "POST",
                data,
              );
              setReq(null);
            })
          }
        />
      )}
      {briefEdit && prd.brief && (
        <BriefEditor
          initial={prd.brief.content}
          busy={busy}
          error={error}
          onClose={() => setBriefEdit(false)}
          onSave={(data) =>
            run(async () => {
              await api(`/prds/${prd.id}/brief`, "PUT", data);
              setBriefEdit(false);
            })
          }
        />
      )}
      {assumption && (
        <Modal title="Edit assumption" onClose={() => setAssumption(null)}>
          <form
            className="modal-body"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await api(
                  `/prds/${prd.id}/assumptions/${assumption.id}`,
                  "PATCH",
                  { content: assumption.content, status: assumption.status },
                );
                setAssumption(null);
              });
            }}
          >
            <Field title="Content">
              <textarea
                required
                rows={5}
                value={assumption.content}
                onChange={(e) =>
                  setAssumption({ ...assumption, content: e.target.value })
                }
              />
            </Field>
            <Field title="Status">
              <select
                value={assumption.status}
                onChange={(e) =>
                  setAssumption({
                    ...assumption,
                    status: e.target.value as Status,
                  })
                }
              >
                {["confirmed", "assumed", "unknown", "rejected"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
            {error && <p className="error-text">{error}</p>}
            <button disabled={busy} className="primary">
              Save assumption
            </button>
          </form>
        </Modal>
      )}
      {fix && (
        <Modal title="Edit suggested change" onClose={() => setFix(null)}>
          <form
            className="modal-body"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await api(`/prds/${prd.id}/review/${fix.id}`, "PATCH", {
                  action: "edit",
                  replacement: fix.text,
                });
                setFix(null);
              });
            }}
          >
            <Field title="Replacement text">
              <textarea
                rows={5}
                required
                value={fix.text}
                onChange={(e) => setFix({ ...fix, text: e.target.value })}
              />
            </Field>
            {error && <p className="error-text">{error}</p>}
            <button className="primary" disabled={busy}>
              Apply change
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}

function QuestionCard({
  question: q,
  index,
  busy,
  onSave,
}: {
  question: Question;
  index: number;
  busy: boolean;
  onSave: (answer: string, status: string) => Promise<void>;
}) {
  const [answer, setAnswer] = useState(q.answer);
  return (
    <article className="question-card">
      <div className="question-number">
        {String(index + 1).padStart(2, "0")}
      </div>
      <div>
        <div className="card-top">
          <span className="eyebrow">{label(q.category)}</span>
          {q.status !== "unanswered" && <Badge value={q.status} />}
        </div>
        <h3>{q.question}</h3>
        <details className="question-reason">
          <summary>Why are we asking this?</summary>
          <p>{q.reason}</p>
        </details>
        <textarea
          aria-label={q.question}
          rows={3}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Your answer…"
        />
        <div className="actions wrap">
          <button
            className="secondary small"
            disabled={busy || !answer.trim()}
            onClick={() => onSave(answer, "answered")}
          >
            <Check size={13} />
            Save answer
          </button>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => {
              setAnswer("");
              onSave("", "unknown");
            }}
          >
            I don’t know
          </button>
          <button
            className="text-button muted"
            disabled={busy}
            onClick={() => {
              setAnswer("");
              onSave("", "skipped");
            }}
          >
            Skip for now
          </button>
        </div>
      </div>
    </article>
  );
}

function RequirementList({
  requirements,
  onEdit,
}: {
  requirements: Requirement[];
  onEdit: (r: Requirement) => void;
}) {
  return (
    <div className="requirements-list">
      {requirements.map((r) => (
        <article className="requirement-card" key={r.id}>
          <div className="card-top">
            <span className="requirement-code">{r.requirement_code}</span>
            <Badge value={r.priority} />
            <button
              className="icon-button"
              onClick={() => onEdit(r)}
              aria-label={`Edit ${r.requirement_code}`}
            >
              <Pencil size={15} />
            </button>
          </div>
          <h3>{r.title}</h3>
          <p>{r.description}</p>
          <h4>Acceptance criteria</h4>
          <ul>
            {r.acceptance_criteria.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
          <details>
            <summary>Dependencies & edge cases</summary>
            <h4>Dependencies</h4>
            <StructuredValue value={r.dependencies} />
            <h4>Edge cases</h4>
            <StructuredValue value={r.edge_cases} />
          </details>
        </article>
      ))}
    </div>
  );
}

function RequirementEditor({
  value,
  busy,
  error,
  onClose,
  onSave,
}: {
  value: Requirement;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSave: (data: Omit<Requirement, "id">) => Promise<void>;
}) {
  const [data, setData] = useState(value);
  return (
    <Modal title="Edit requirement" onClose={onClose}>
      <form
        className="modal-body"
        onSubmit={(e) => {
          e.preventDefault();
          const { id: _id, ...rest } = data;
          void _id;
          const keys = [
            "requirement_code",
            "title",
            "description",
            "type",
            "priority",
            "acceptance_criteria",
            "dependencies",
            "edge_cases",
          ];
          onSave(
            Object.fromEntries(
              Object.entries(rest).filter(([k]) => keys.includes(k)),
            ) as Omit<Requirement, "id">,
          );
        }}
      >
        {["requirement_code", "title", "description"].map((k) => (
          <Field title={label(k)} key={k}>
            <textarea
              required
              rows={k === "description" ? 3 : 1}
              value={String(data[k as keyof Requirement])}
              onChange={(e) => setData({ ...data, [k]: e.target.value })}
            />
          </Field>
        ))}
        <div className="form-grid">
          <Field title="Type">
            <select
              value={data.type}
              onChange={(e) => setData({ ...data, type: e.target.value })}
            >
              {[
                "functional",
                "non_functional",
                "data",
                "ai_ml",
                "analytics",
                "security",
                "compliance",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
          <Field title="Priority">
            <select
              value={data.priority}
              onChange={(e) => setData({ ...data, priority: e.target.value })}
            >
              {["must", "should", "could", "wont"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
        </div>
        {(["acceptance_criteria", "dependencies", "edge_cases"] as const).map(
          (k) => (
            <Field key={k} title={`${label(k)} · one per line`}>
              <textarea
                rows={4}
                required={k === "acceptance_criteria"}
                value={data[k].join("\n")}
                onChange={(e) =>
                  setData({ ...data, [k]: e.target.value.split("\n") })
                }
              />
            </Field>
          ),
        )}
        {error && <p className="error-text">{error}</p>}
        <button className="primary" disabled={busy}>
          Save requirement
        </button>
      </form>
    </Modal>
  );
}

function BriefEditor({
  initial,
  busy,
  error,
  onClose,
  onSave,
}: {
  initial: Brief;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSave: (data: Brief) => Promise<void>;
}) {
  const [data, setData] = useState(initial);
  return (
    <Modal title="Edit product brief" onClose={onClose}>
      <form
        className="modal-body"
        onSubmit={(e) => {
          e.preventDefault();
          onSave(data);
        }}
      >
        {Object.entries(data)
          .filter(([key]) => key !== "assumptions")
          .map(([key, value]) => (
            <Field
              key={key}
              title={`${label(key)}${Array.isArray(value) ? " · one per line" : ""}`}
            >
              <textarea
                rows={3}
                value={Array.isArray(value) ? value.join("\n") : value}
                onChange={(e) =>
                  setData({
                    ...data,
                    [key]: Array.isArray(value)
                      ? e.target.value.split("\n").filter(Boolean)
                      : e.target.value,
                  })
                }
              />
            </Field>
          ))}
        <p className="notice">
          Manage assumptions in the dedicated ledger. Editing the brief does not
          silently remove them.
        </p>
        {error && <p className="error-text">{error}</p>}
        <button className="primary" disabled={busy}>
          Save brief
        </button>
      </form>
    </Modal>
  );
}
