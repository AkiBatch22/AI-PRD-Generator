"use client";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Product, Organization, label } from "@/lib/types";
import { api } from "@/lib/api";
import { Field, Modal, Empty, Spinner } from "./ui";

export function Products({
  org,
  products,
  onUpdate,
}: {
  org: Organization;
  products: Product[];
  onUpdate: () => Promise<void>;
}) {
  const [editing, setEditing] = useState<Partial<Product> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <h1>Products</h1>
          <p>
            Specific product knowledge, grounded in shared organization context.
          </p>
        </div>
        <button
          className="primary"
          disabled={!org.blueprint_validated}
          onClick={() =>
            setEditing({ organization_id: org.id, name: "", description: "" })
          }
        >
          <Plus size={16} />
          Add product
        </button>
      </div>
      {!org.blueprint_validated && (
        <p className="notice">
          Validate your company blueprint before adding products.
        </p>
      )}
      <div className="product-grid">
        {products.map((p) => (
          <button
            className="product-card"
            key={p.id}
            onClick={() => setEditing(p)}
          >
            <h2>{p.name}</h2>
            <p>{p.description}</p>
          </button>
        ))}
      </div>
      {!products.length && (
        <Empty title="Add your first product">
          Define who it serves and what it should achieve.
        </Empty>
      )}
      {editing && (
        <Modal
          title={editing.id ? "Product context" : "Add product"}
          onClose={() => setEditing(null)}
        >
          <form
            className="modal-body"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                const { id, ...values } = editing;
                const allowed = [
                  "organization_id",
                  "name",
                  "description",
                  "users",
                  "primary_goal",
                  "current_user_journey",
                  "major_features",
                  "business_metrics",
                  "constraints",
                  "technical_context",
                ];
                await api(
                  id ? `/products/${id}` : "/products",
                  id ? "PUT" : "POST",
                  Object.fromEntries(
                    Object.entries(values).filter(([k]) => allowed.includes(k)),
                  ),
                );
                await onUpdate();
                setEditing(null);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {[
              "name",
              "description",
              "users",
              "primary_goal",
              "current_user_journey",
              "major_features",
              "business_metrics",
              "constraints",
              "technical_context",
            ].map((k) => (
              <Field key={k} title={label(k)}>
                {k === "name" ? (
                  <input
                    required
                    value={editing[k] || ""}
                    onChange={(e) =>
                      setEditing({ ...editing, [k]: e.target.value })
                    }
                  />
                ) : (
                  <textarea
                    rows={2}
                    value={String(editing[k as keyof Product] || "")}
                    onChange={(e) =>
                      setEditing({ ...editing, [k]: e.target.value })
                    }
                    placeholder="Leave blank if not yet known"
                  />
                )}
              </Field>
            ))}
            {error && (
              <p role="alert" className="error-text">
                {error}
              </p>
            )}
            <button disabled={busy} className="primary">
              {busy && <Spinner />}Save product
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
