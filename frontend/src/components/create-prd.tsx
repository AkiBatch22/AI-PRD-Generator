"use client";
import { useEffect, useState } from "react";
import { ArrowLeft, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Product, PRD } from "@/lib/types";
import { Field, Modal, Spinner, StructuredValue } from "./ui";

export function CreatePRD({
  products,
  onClose,
  onCreate,
}: {
  products: Product[];
  onClose: () => void;
  onCreate: (p: PRD) => void;
}) {
  const [productId, setProductId] = useState(products[0]?.id || "");
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [ai, setAi] = useState(false);
  const [context, setContext] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    setContext(null);
    const timer = setTimeout(() => {
      api<Record<string, unknown>>(
        `/products/${productId}/context?query=${encodeURIComponent(idea)}`,
      )
        .then((data) => {
          if (!cancelled) setContext(data);
        })
        .catch((e) => {
          if (!cancelled) setError(e.message);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [productId, idea]);
  return (
    <Modal title="New PRD" onClose={onClose}>
      <form
        className="modal-body"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const p = await api<PRD>("/prds", "POST", {
              product_id: productId,
              title,
              idea,
              ai_relevant: ai,
            });
            onCreate(p);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <p className="muted">
          Start with an idea. Your copilot will help uncover what is missing.
        </p>
        <Field title="Product">
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          >
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
        <details className="context-used">
          <summary>Context supplied to the AI</summary>
          <StructuredValue value={context} />
        </details>
        <Field title="Initiative title">
          <input
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Home Loan Readiness Score"
          />
        </Field>
        <Field title="Describe your idea">
          <textarea
            required
            minLength={10}
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="What would you like to build, and why?"
            rows={4}
          />
        </Field>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={ai}
            onChange={(e) => setAi(e.target.checked)}
          />
          This feature includes AI / ML behavior
        </label>
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
        <div className="form-footer">
          <button type="button" className="secondary" onClick={onClose}>
            <ArrowLeft size={15} />
            Cancel
          </button>
          <button className="primary" disabled={busy || !context}>
            {busy ? <Spinner /> : <Sparkles size={16} />}Create & explore
          </button>
        </div>
      </form>
    </Modal>
  );
}
