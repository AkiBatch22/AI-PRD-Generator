"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Plus,
  Check,
  Upload,
  Pencil,
  X,
  BookOpen,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  ContextItem,
  Organization,
  Rule,
  categories,
  label,
  Status,
} from "@/lib/types";
import { Badge, Empty, Field, Modal, Spinner } from "./ui";

export function Knowledge({
  org,
  onUpdate,
}: {
  org: Organization;
  onUpdate: () => Promise<void>;
}) {
  const [items, setItems] = useState<ContextItem[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [filter, setFilter] = useState("all");
  const [editing, setEditing] = useState<Partial<ContextItem> | null>(null);
  const [importing, setImporting] = useState(false);
  const [ruleForm, setRuleForm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [i, r] = await Promise.all([
      api<ContextItem[]>(`/organizations/${org.id}/context`),
      api<Rule[]>(`/organizations/${org.id}/rules`),
    ]);
    setItems(i);
    setRules(r);
  }, [org.id]);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
      await onUpdate();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const changeStatus = (item: ContextItem, status: Status) =>
    run(() =>
      api(`/organizations/${org.id}/context/${item.id}`, "PATCH", { status }),
    );
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <h1>
            {org.blueprint_validated
              ? "Organization context"
              : "Company blueprint"}
          </h1>
          <p>
            {org.blueprint_validated
              ? "The knowledge behind every product decision."
              : "Review this understanding before it becomes organization context."}
          </p>
        </div>
        <div className="actions">
          <button className="secondary" onClick={() => setImporting(true)}>
            <Upload size={16} />
            Import
          </button>
          <button
            className="primary"
            onClick={() =>
              setEditing({
                category: "overview",
                status: "confirmed",
                title: "",
                content: "",
              })
            }
          >
            <Plus size={16} />
            Add context
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {!org.blueprint_validated && (
        <div className="validation-banner">
          <BookOpen size={21} />
          <div>
            <strong>Validate your company blueprint</strong>
            <p>
              Confirm facts, review AI assumptions, and leave undecided topics
              unresolved.
            </p>
          </div>
          <button
            disabled={busy || !items.some((i) => i.status === "confirmed")}
            className="primary"
            onClick={() =>
              run(() => api(`/organizations/${org.id}/validate`, "POST"))
            }
          >
            Validate blueprint
            <Check size={16} />
          </button>
        </div>
      )}
      <div className="knowledge-layout">
        <div className="context-toolbar">
          <label>
            Category{" "}
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All context</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {label(c)}
                </option>
              ))}
            </select>
          </label>
          <span className="muted">
            Context completeness: {org.maturity?.overall || 0}%
          </span>
        </div>
        <div>
          <div className="context-items">
            {items
              .filter((i) => filter === "all" || i.category === filter)
              .map((item) => (
                <article
                  key={item.id}
                  className={`context-card ${item.status === "rejected" ? "faded" : ""}`}
                >
                  <div className="card-top">
                    <span className="eyebrow">{label(item.category)}</span>
                    <Badge value={item.status} />
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.content || "Not decided yet"}</p>
                  <div className="card-footer">
                    <span className="muted">
                      Source: {item.source} ·{" "}
                      {Math.round(item.confidence * 100)}% extraction confidence
                    </span>
                    <div className="actions">
                      {item.status !== "confirmed" && (
                        <button
                          disabled={busy}
                          className="text-button"
                          onClick={() => changeStatus(item, "confirmed")}
                        >
                          <Check size={14} />
                          Confirm
                        </button>
                      )}
                      <button
                        className="text-button"
                        onClick={() => setEditing(item)}
                      >
                        <Pencil size={14} />
                        Edit
                      </button>
                      {item.status !== "rejected" && (
                        <button
                          disabled={busy}
                          className="text-button muted"
                          onClick={() => changeStatus(item, "rejected")}
                        >
                          <X size={14} />
                          Reject
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            {!items.filter((i) => filter === "all" || i.category === filter)
              .length && (
              <Empty title="No context here yet">
                Add a fact, import a document, or record an open question.
              </Empty>
            )}
          </div>
          {(filter === "all" || filter === "rules") && (
            <section className="rules-section">
              <div className="section-title">
                <h2>
                  <ShieldCheck size={20} />
                  Global product rules
                </h2>
                <button
                  className="text-button"
                  onClick={() => setRuleForm(true)}
                >
                  <Plus size={16} />
                  Add rule
                </button>
              </div>
              {rules.map((rule) => (
                <div className="rule-row" key={rule.id}>
                  <Badge value={rule.kind} />
                  <p>{rule.content}</p>
                  <button
                    aria-label={`Delete rule ${rule.content}`}
                    className="icon-button"
                    disabled={busy}
                    onClick={() =>
                      run(() =>
                        api(
                          `/organizations/${org.id}/rules/${rule.id}`,
                          "DELETE",
                        ),
                      )
                    }
                  >
                    <X size={15} />
                  </button>
                </div>
              ))}
              {!rules.length && (
                <Empty title="Define the boundaries">
                  Rules will be supplied to discovery and checked during PRD
                  review.
                </Empty>
              )}
            </section>
          )}
        </div>
      </div>
      {editing && (
        <Modal
          title={editing.id ? "Edit context" : "Add context"}
          onClose={() => setEditing(null)}
        >
          <form
            className="modal-body"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await api(
                  `/organizations/${org.id}/context${editing.id ? "/" + editing.id : ""}`,
                  editing.id ? "PATCH" : "POST",
                  editing.id
                    ? { content: editing.content, status: editing.status }
                    : {
                        ...editing,
                        source: "user",
                        confidence: editing.status === "confirmed" ? 1 : 0,
                      },
                );
                setEditing(null);
              });
            }}
          >
            <Field title="Category">
              <select
                disabled={!!editing.id}
                value={editing.category}
                onChange={(e) =>
                  setEditing({ ...editing, category: e.target.value })
                }
              >
                {categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field title="Title">
              <input
                required
                disabled={!!editing.id}
                value={editing.title}
                onChange={(e) =>
                  setEditing({ ...editing, title: e.target.value })
                }
              />
            </Field>
            <Field title="What do we know?">
              <textarea
                rows={4}
                required
                value={editing.content}
                onChange={(e) =>
                  setEditing({ ...editing, content: e.target.value })
                }
              />
            </Field>
            <Field title="Status">
              <select
                value={editing.status}
                onChange={(e) =>
                  setEditing({ ...editing, status: e.target.value as Status })
                }
              >
                {["confirmed", "assumed", "unknown", "rejected"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </Field>
            {error && <p className="error-text">{error}</p>}
            <button className="primary" disabled={busy}>
              {busy ? <Spinner /> : <Check size={16} />}Save context
            </button>
          </form>
        </Modal>
      )}
      {importing && (
        <ImportDialog
          orgId={org.id}
          onClose={() => setImporting(false)}
          onDone={async () => {
            await load();
            await onUpdate();
            setImporting(false);
          }}
        />
      )}
      {ruleForm && (
        <Modal title="Add organization rule" onClose={() => setRuleForm(false)}>
          <form
            className="modal-body"
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              run(async () => {
                await api(`/organizations/${org.id}/rules`, "POST", {
                  kind: data.get("kind"),
                  content: data.get("content"),
                });
                setRuleForm(false);
              });
            }}
          >
            <Field title="Rule type">
              <select name="kind">
                <option value="must">Must</option>
                <option value="must_not">Must not</option>
              </select>
            </Field>
            <Field title="Rule">
              <textarea
                name="content"
                minLength={3}
                required
                placeholder="Every feature requires analytics events"
              />
            </Field>
            <button className="primary" disabled={busy}>
              Save rule
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}

function ImportDialog({
  orgId,
  onClose,
  onDone,
}: {
  orgId: string;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal title="Import organization knowledge" onClose={onClose}>
      <form
        className="modal-body"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            if (file) {
              const data = new FormData();
              data.append("file", file);
              await api(`/organizations/${orgId}/documents`, "POST", data);
            } else
              await api(`/organizations/${orgId}/import`, "POST", { text });
            await onDone();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <p className="notice">
          Imported context is a candidate, never a confirmed fact. Review each
          extracted item before using it.
        </p>
        <Field title="Paste documentation or an existing PRD">
          <textarea
            rows={8}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Company overview, product notes, business rules…"
          />
        </Field>
        <Field title="Or upload a document">
          <input
            type="file"
            accept=".txt,.md,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </Field>
        <small className="muted">
          Text, Markdown, or text-based PDF · Up to 5 MB / 100 pages
        </small>
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
        <button disabled={busy || (!file && !text.trim())} className="primary">
          {busy ? <Spinner /> : <Upload size={16} />}Extract candidate context
        </button>
      </form>
    </Modal>
  );
}
