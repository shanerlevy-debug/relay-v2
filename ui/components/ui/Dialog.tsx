"use client";

import { X } from "lucide-react";
import { ReactNode, useEffect, useRef } from "react";

/**
 * Modal dialog built on the native HTML <dialog> element — gives us:
 *  - Built-in focus trap
 *  - Escape-to-close
 *  - Backdrop overlay (the `::backdrop` pseudo-element)
 *  - Proper accessibility semantics
 *
 * No external library, no Radix, no headless-ui — just CSS + the
 * built-in element. Lightweight and modern.
 */
interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  /** Max content width in px (excluding padding). Default 480. */
  maxWidth?: number;
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  maxWidth = 480,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) {
      dlg.showModal();
    } else if (!open && dlg.open) {
      dlg.close();
    }
  }, [open]);

  // Wire up close events from inside the dialog (Escape key, backdrop click)
  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    const handleClose = () => onClose();
    dlg.addEventListener("close", handleClose);
    return () => dlg.removeEventListener("close", handleClose);
  }, [onClose]);

  // Close on backdrop click
  function onBackdropClick(e: React.MouseEvent<HTMLDialogElement>) {
    if (e.target === ref.current) {
      onClose();
    }
  }

  return (
    <dialog
      ref={ref}
      onClick={onBackdropClick}
      style={{
        padding: 0,
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        background: "var(--color-surface-2)",
        color: "var(--color-fg1)",
        width: "100%",
        maxWidth,
        boxShadow: "var(--shadow-3)",
      }}
    >
      <div style={{ padding: "20px 24px 8px 24px", display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>
            {title}
          </h2>
          {description && (
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--color-fg3)", lineHeight: 1.5 }}>
              {description}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          style={{
            background: "transparent",
            border: "none",
            cursor: "pointer",
            padding: 4,
            color: "var(--color-fg3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 4,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--color-surface-3)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          <X size={16} />
        </button>
      </div>

      <div style={{ padding: "12px 24px 24px 24px" }}>{children}</div>

      {/* Backdrop styling */}
      <style>{`
        dialog::backdrop {
          background: rgba(8, 11, 15, 0.55);
          backdrop-filter: blur(4px);
        }
      `}</style>
    </dialog>
  );
}
