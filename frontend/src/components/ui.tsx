"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { X, LoaderCircle } from "lucide-react";
import { label } from "@/lib/types";

export function Badge({ value }: { value: string }) {
  return <span className={`badge ${value}`}>{label(value)}</span>;
}
export function Field({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{title}</span>
      {children}
    </label>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Spinner() {
  return <LoaderCircle className="spin" size={16} aria-label="Loading" />;
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function StructuredValue({ value }: { value: unknown }) {
  if (Array.isArray(value))
    return (
      <ul className="content-list">
        {value.map((v, i) => (
          <li key={i}>
            <StructuredValue value={v} />
          </li>
        ))}
      </ul>
    );
  if (value && typeof value === "object")
    return (
      <div>
        {Object.entries(value).map(([k, v]) => (
          <div key={k} className="structured-row">
            <strong>{label(k)}</strong>
            <StructuredValue value={v} />
          </div>
        ))}
      </div>
    );
  return <p>{String(value ?? "Not yet defined")}</p>;
}
