"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { Organization, Product, PRD } from "@/lib/types";
import { Badge, Empty, Spinner } from "./ui";
import { CreatePRD } from "./create-prd";
import { Knowledge } from "./knowledge";
import { Onboarding } from "./onboarding";
import { Products } from "./products";
import { Workspace } from "./workspace";

type View = "prds" | "context" | "products" | "onboarding";

export default function App() {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [orgId, setOrgId] = useState("");
  const [org, setOrg] = useState<Organization | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [prds, setPrds] = useState<PRD[]>([]);
  const [view, setView] = useState<View>("prds");
  const [activePrd, setActivePrd] = useState<PRD | null>(null);
  const [newPrd, setNewPrd] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [provider, setProvider] = useState("");

  const loadWorkspace = useCallback(async (id: string) => {
    const [organization, productList, prdList] = await Promise.all([
      api<Organization>(`/organizations/${id}`),
      api<Product[]>(`/products?organization_id=${id}`),
      api<PRD[]>(`/prds?organization_id=${id}`),
    ]);
    return { organization, productList, prdList };
  }, []);

  const refresh = async () => {
    const data = await loadWorkspace(orgId);
    setOrg(data.organization);
    setProducts(data.productList);
    setPrds(data.prdList);
  };

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api<Organization[]>("/organizations"),
      api<{ provider: string }>("/health"),
    ])
      .then(([list, health]) => {
        if (cancelled) return;
        setOrgs(list);
        setOrgId(list[0]?.id || "");
        setProvider(health.provider);
        if (!list.length) {
          setView("onboarding");
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    setLoading(true);
    loadWorkspace(orgId)
      .then((data) => {
        if (cancelled) return;
        setOrg(data.organization);
        setProducts(data.productList);
        setPrds(data.prdList);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId, loadWorkspace]);

  function navigate(next: View) {
    setActivePrd(null);
    setView(next);
    setError("");
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <button className="brand" onClick={() => navigate("prds")}>
          Context
        </button>
        <select
          aria-label="Organization"
          value={orgId}
          onChange={(e) => {
            setOrgId(e.target.value);
            setActivePrd(null);
            setError("");
          }}
        >
          {!orgs.length && <option value="">New workspace</option>}
          {orgs.map((o) => (
            <option value={o.id} key={o.id}>
              {o.name}
            </option>
          ))}
        </select>
        <span className="muted">
          {provider === "mock" ? "Demo AI" : provider ? "Connected AI" : ""}
        </span>
        <button className="text-button" onClick={() => navigate("onboarding")}>
          New organization
        </button>
      </header>
      <nav className="main-nav" aria-label="Workspace">
        {(["prds", "context", "products"] as const).map((item) => (
          <button
            key={item}
            className={view === item ? "active" : ""}
            aria-current={view === item ? "page" : undefined}
            onClick={() => navigate(item)}
          >
            {item === "prds"
              ? "PRDs"
              : item === "context"
                ? "Context"
                : "Products"}
          </button>
        ))}
      </nav>
      <main>
        {error && (
          <div role="alert" className="error-banner">
            {error}
            <button onClick={() => window.location.reload()}>Reload</button>
          </div>
        )}
        {loading ? (
          <div className="loading">
            <Spinner />
            Loading workspace…
          </div>
        ) : activePrd ? (
          <Workspace
            key={activePrd.id}
            initial={activePrd}
            onBack={() => {
              setActivePrd(null);
              refresh().catch((e) => setError(e.message));
            }}
            onChange={(p) =>
              setPrds((old) => old.map((v) => (v.id === p.id ? p : v)))
            }
          />
        ) : view === "onboarding" ? (
          <Onboarding
            onComplete={async (organization) => {
              setOrgs((list) =>
                list.some((o) => o.id === organization.id)
                  ? list
                  : [...list, organization],
              );
              setOrgId(organization.id);
              setView("context");
            }}
          />
        ) : org ? (
          <>
            {view === "prds" && (
              <div className="page">
                <div className="page-heading">
                  <div>
                    <h1>PRDs</h1>
                    <p>Discover, define, and review your next feature.</p>
                  </div>
                  <button
                    className="primary"
                    disabled={!org.blueprint_validated || !products.length}
                    onClick={() => setNewPrd(true)}
                  >
                    <Plus size={16} />
                    New PRD
                  </button>
                </div>
                {!org.blueprint_validated ? (
                  <p className="notice">
                    First,{" "}
                    <button
                      className="text-button"
                      onClick={() => navigate("context")}
                    >
                      validate your organization context
                    </button>
                    .
                  </p>
                ) : !products.length ? (
                  <p className="notice">
                    <button
                      className="text-button"
                      onClick={() => navigate("products")}
                    >
                      Add a product
                    </button>{" "}
                    before creating a PRD.
                  </p>
                ) : null}
                {!prds.length ? (
                  <Empty title="No PRDs yet">
                    Create one to start discovery.
                  </Empty>
                ) : (
                  <div className="document-list">
                    {prds.map((p) => (
                      <button
                        className="document-row"
                        key={p.id}
                        onClick={() => setActivePrd(p)}
                      >
                        <div>
                          <strong>{p.title}</strong>
                          <small>
                            {products.find((x) => x.id === p.product_id)?.name}
                          </small>
                        </div>
                        <Badge value={p.status} />
                        <span className="muted">{p.quality.overall}/100</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {view === "context" && <Knowledge org={org} onUpdate={refresh} />}
            {view === "products" && (
              <Products org={org} products={products} onUpdate={refresh} />
            )}
          </>
        ) : null}
      </main>
      {newPrd && (
        <CreatePRD
          products={products}
          onClose={() => setNewPrd(false)}
          onCreate={(p) => {
            setNewPrd(false);
            setActivePrd(p);
            setPrds((old) => [p, ...old]);
          }}
        />
      )}
    </div>
  );
}
