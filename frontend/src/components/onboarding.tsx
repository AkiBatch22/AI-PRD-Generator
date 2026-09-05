"use client";
import { useState } from "react";
import {
  Building2,
  Lightbulb,
  MessagesSquare,
  ArrowRight,
  Sparkles,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import { Organization } from "@/lib/types";
import { Field, Spinner } from "./ui";

const greenfield = [
  ["Initial idea", "overview"],
  ["Problem", "overview"],
  ["Target user", "customers"],
  ["Current alternative", "products"],
  ["Value proposition", "overview"],
  ["Geography / market", "industry"],
  ["Business model", "business_model"],
  ["Product scope", "products"],
  ["Product principles", "principles"],
  ["Constraints", "compliance"],
  ["Success metrics", "metrics"],
  ["Technology, if known", "technology"],
];
const limited = [
  ["What the company does", "overview"],
  ["Target users", "customers"],
  ["Buyer versus user", "customers"],
  ["Current products", "products"],
  ["Existing user journey", "products"],
  ["Business model", "business_model"],
  ["Key metrics", "metrics"],
  ["Technical architecture", "technology"],
  ["Regulatory constraints", "compliance"],
  ["Major business rules", "rules"],
  ["Product principles", "principles"],
];
const established = [
  ["Organization description", "overview"],
  ["Industry", "industry"],
  ["Geography", "industry"],
  ["Customer segments", "customers"],
  ["Business model", "business_model"],
  ["Major products", "products"],
  ["Business metrics", "metrics"],
  ["Technology stack", "technology"],
  ["Compliance constraints", "compliance"],
  ["Product principles", "principles"],
  ["Terminology", "terminology"],
];

export function Onboarding({
  onComplete,
}: {
  onComplete: (o: Organization) => Promise<void>;
}) {
  const [mode, setMode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [org, setOrg] = useState<Organization | null>(null);
  const [stage, setStage] = useState(0);
  const [answer, setAnswer] = useState("");
  const [assumed, setAssumed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [help, setHelp] = useState("");
  const stages =
    mode === "greenfield"
      ? greenfield
      : mode === "limited"
        ? limited
        : established;
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = (status: string) =>
    run(async () => {
      if (!org) return;
      await api(`/organizations/${org.id}/context`, "POST", {
        category: stages[stage][1],
        title: stages[stage][0],
        content: status === "unknown" ? "Not decided yet" : answer,
        status,
        source: assumed && status !== "unknown" ? "ai" : "user",
        confidence: status === "confirmed" ? 1 : 0,
      });
      if (stage === stages.length - 1) await onComplete(org);
      else {
        setStage(stage + 1);
        setAnswer("");
        setAssumed(false);
        setHelp("");
      }
    });
  return (
    <div className="page onboarding">
      <h1>
        {!org
          ? "How much context do you already have?"
          : mode === "greenfield"
            ? "Let’s shape your company blueprint."
            : "Make what you know explicit."}
      </h1>
      <p className="intro">
        {!org
          ? "Start where you are. Your copilot will meet you there."
          : "You can leave any topic unresolved. Nothing becomes organization context until you validate it."}
      </p>
      {!org ? (
        <>
          <div className="onboarding-options">
            {[
              {
                id: "established",
                icon: Building2,
                title: "Established organization",
                text: "Import existing company and product context.",
              },
              {
                id: "limited",
                icon: MessagesSquare,
                title: "Existing product, limited docs",
                text: "Help structure what we already know.",
              },
              {
                id: "greenfield",
                icon: Lightbulb,
                title: "Starting from an idea",
                text: "Build company and product context from scratch.",
              },
            ].map((option) => (
              <button
                className={`path-card ${mode === option.id ? "chosen" : ""}`}
                key={option.id}
                onClick={() => setMode(option.id)}
              >
                <option.icon size={27} />
                <h3>{option.title}</h3>
                <p>{option.text}</p>
                {mode === option.id && (
                  <Check className="choice-check" size={18} />
                )}
              </button>
            ))}
          </div>
          {mode && (
            <form
              className="onboarding-form"
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  const created = await api<Organization>(
                    "/organizations",
                    "POST",
                    { name, description, mode },
                  );
                  setOrg(created);
                  if (mode === "greenfield") setAnswer(description);
                });
              }}
            >
              <Field title="Organization name">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="A working name is fine"
                />
              </Field>
              <Field
                title={
                  mode === "greenfield"
                    ? "Your initial idea"
                    : "What does your organization do?"
                }
              >
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                />
              </Field>
              <button className="primary" disabled={busy}>
                {busy ? <Spinner /> : <ArrowRight size={16} />}Start{" "}
                {mode === "established" ? "context setup" : "discovery"}
              </button>
            </form>
          )}
        </>
      ) : (
        <div className="discovery-onboarding">
          <section className="interview-card">
            <div className="eyebrow">
              STEP {stage + 1} OF {stages.length}
            </div>
            <h2>{stages[stage][0]}</h2>
            <p className="muted">
              {mode === "greenfield"
                ? "What is your current thinking? A starting hypothesis is welcome."
                : "Describe what is known today, including any important limitations."}
            </p>
            <textarea
              aria-label={stages[stage][0]}
              value={answer}
              onChange={(e) => {
                setAnswer(e.target.value);
              }}
              rows={6}
              placeholder="I know the answer…"
            />
            {assumed && (
              <p className="notice">
                This suggestion will be saved as an AI assumption for review.
              </p>
            )}
            {help && <p className="notice">{help}</p>}
            <div className="actions wrap">
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const result = await api<{
                      suggestion: string;
                      rationale: string;
                    }>(`/organizations/${org.id}/help`, "POST", {
                      stage: stages[stage][0],
                      idea: description,
                    });
                    setAnswer(result.suggestion);
                    setHelp(result.rationale);
                    setAssumed(true);
                  })
                }
              >
                <Sparkles size={15} />
                Help me define it
              </button>
              <button
                className="text-button"
                disabled={busy}
                onClick={() => save("unknown")}
              >
                {mode === "greenfield"
                  ? "Not decided yet"
                  : "I don't know / skip"}
              </button>
            </div>
            <div className="form-footer">
              <span className="muted">
                {mode === "established"
                  ? "You can import documents after setup."
                  : "Answers are saved as you continue."}
              </span>
              <button
                className="primary"
                disabled={busy || !answer.trim()}
                onClick={() => save(assumed ? "assumed" : "confirmed")}
              >
                {busy ? <Spinner /> : <ArrowRight size={16} />}{" "}
                {stage === stages.length - 1
                  ? "Review blueprint"
                  : "Save & continue"}
              </button>
            </div>
            {mode === "established" && (
              <button
                className="text-button"
                disabled={busy}
                onClick={() => run(() => onComplete(org))}
              >
                Continue to document import
              </button>
            )}
          </section>
        </div>
      )}
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
    </div>
  );
}
