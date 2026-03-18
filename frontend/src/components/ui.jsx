import { Children, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, X } from "lucide-react";

import { cn } from "@/utils";

const BUTTON_STYLES = {
  primary:
    "bg-teal/85 text-shell font-semibold hover:bg-teal/95",
  secondary:
    "border border-white/7 bg-white/[0.04] text-ink hover:bg-white/[0.07] hover:border-white/10",
  ghost:
    "bg-transparent text-muted hover:text-ink hover:bg-white/[0.04]",
  danger:
    "bg-coral/80 text-shell font-semibold hover:bg-coral/90",
  subtle:
    "border border-white/5 bg-white/[0.03] text-muted hover:bg-white/[0.06] hover:text-ink",
};

const BUTTON_SIZES = {
  sm: "h-9 px-3.5 text-[13px]",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
};

const CONTROL_BASE =
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/15 focus-visible:ring-offset-1 focus-visible:ring-offset-shell disabled:cursor-not-allowed disabled:opacity-50 transition-colors duration-150 ease-out";

export function Button({
  className,
  variant = "primary",
  size = "md",
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      className={cn(CONTROL_BASE, BUTTON_STYLES[variant], BUTTON_SIZES[size], className)}
      {...props}
    />
  );
}

export function LinkButton({
  className,
  variant = "secondary",
  size = "md",
  children,
  ...props
}) {
  return (
    <a className={cn(CONTROL_BASE, BUTTON_STYLES[variant], BUTTON_SIZES[size], className)} {...props}>
      {children}
    </a>
  );
}

export function Card({ className, children, ...props }) {
  return (
    <section className={cn("glass-card rounded-2xl p-5", className)} {...props}>
      {children}
    </section>
  );
}

export function PageHeader({ title, description, actions, eyebrow }) {
  return (
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div className="max-w-3xl space-y-1.5">
        {eyebrow ? (
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal/80">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          {title}
        </h1>
        {description ? <p className="max-w-2xl text-sm text-muted/80">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function SectionHeading({ title, description, action }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="space-y-0.5">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {description ? <p className="text-[13px] text-muted/70">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function MetricCard({ label, value, note, tone = "neutral" }) {
  const toneAccent = {
    neutral: "border-white/5",
    sky: "border-sky/12",
    success: "border-teal/12",
    amber: "border-amber/12",
    danger: "border-coral/12",
  };

  const toneGlow = {
    neutral: "",
    sky: "",
    success: "",
    amber: "",
    danger: "",
  };

  return (
    <div className={cn("glass-card-soft rounded-2xl p-4", toneAccent[tone], toneGlow[tone])}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted/70">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-ink">{value}</p>
      {note ? <p className="mt-1.5 text-[13px] text-muted/60">{note}</p> : null}
    </div>
  );
}

export function Badge({ children, tone = "neutral", className }) {
  const toneClasses = {
    neutral: "border-white/8 bg-white/5 text-muted",
    sky: "border-sky/15 bg-sky/8 text-sky",
    success: "border-teal/15 bg-teal/8 text-teal",
    amber: "border-amber/15 bg-amber/8 text-amber",
    danger: "border-coral/15 bg-coral/8 text-coral",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-lg border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide",
        toneClasses[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

export function Field({ label, hint, htmlFor, children, className }) {
  return (
    <label className={cn("grid gap-1.5 text-sm", className)} htmlFor={htmlFor}>
      <span className="text-[13px] font-medium text-ink/80">{label}</span>
      {children}
      {hint ? <span className="text-[12px] text-muted/60">{hint}</span> : null}
    </label>
  );
}

const INPUT_BASE =
  "glass-input disabled:cursor-not-allowed disabled:opacity-50";

export function TextInput({ className, ...props }) {
  return <input className={cn(INPUT_BASE, className)} {...props} />;
}

export function TextArea({ className, rows = 4, ...props }) {
  return (
    <textarea className={cn(INPUT_BASE, "min-h-28 resize-y", className)} rows={rows} {...props} />
  );
}

export function TagInput({ tags = [], onChange, placeholder = "Eingabe + Enter", tone = "neutral" }) {
  const [input, setInput] = useState("");
  const inputRef = useRef(null);

  const toneClasses = {
    neutral: "border-white/8 bg-white/5 text-muted",
    sky: "border-sky/15 bg-sky/8 text-sky",
    success: "border-teal/15 bg-teal/8 text-teal",
    amber: "border-amber/15 bg-amber/8 text-amber",
    danger: "border-coral/15 bg-coral/8 text-coral",
  };

  function addTag(value) {
    const trimmed = value.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInput("");
  }

  function removeTag(index) {
    onChange(tags.filter((_, i) => i !== index));
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addTag(input);
    }
  }

  function handlePaste(event) {
    event.preventDefault();
    const pasted = event.clipboardData.getData("text");
    const newTags = pasted
      .split(/[\n,;]+/)
      .map((t) => t.trim())
      .filter((t) => t && !tags.includes(t));
    if (newTags.length > 0) {
      onChange([...tags, ...newTags]);
    }
  }

  return (
    <div
      className="glass-input flex min-h-11 cursor-text flex-wrap items-center gap-1.5 !py-2"
      onClick={() => inputRef.current?.focus()}
    >
      {tags.map((tag, index) => (
        <span
          key={`${tag}-${index}`}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[12px] font-medium leading-tight select-none",
            toneClasses[tone]
          )}
          onClick={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {tag}
          <span
            role="button"
            tabIndex={0}
            className="ml-0.5 cursor-pointer rounded-sm p-0.5 opacity-60 transition-opacity hover:opacity-100"
            onClick={(e) => {
              e.stopPropagation();
              removeTag(index);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                removeTag(index);
              }
            }}
          >
            <X size={10} />
          </span>
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        className="min-w-[8rem] flex-1 border-none bg-transparent text-[13px] text-ink outline-none placeholder:text-muted/40"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={() => { if (input.trim()) addTag(input); }}
        placeholder={tags.length === 0 ? placeholder : ""}
      />
    </div>
  );
}

export function SelectInput({ className, children, value, onChange, disabled, ...props }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const [pos, setPos] = useState(null);

  // Parse <option> children into data
  const options = [];
  Children.forEach(children, (child) => {
    if (child?.type === "option") {
      options.push({
        value: child.props.value ?? "",
        label: child.props.children ?? "",
        disabled: child.props.disabled,
      });
    }
  });

  const selectedLabel =
    options.find((o) => String(o.value) === String(value))?.label ??
    options[0]?.label ??
    "";

  // Position the portal panel relative to the trigger
  useEffect(() => {
    if (!open || !triggerRef.current) return;
    function sync() {
      const rect = triggerRef.current.getBoundingClientRect();
      const flipUp = window.innerHeight - rect.bottom < 200 && rect.top > 200;
      setPos({
        position: "fixed",
        left: rect.left,
        minWidth: rect.width,
        zIndex: 9999,
        ...(flipUp
          ? { bottom: window.innerHeight - rect.top + 6 }
          : { top: rect.bottom + 6 }),
      });
    }
    sync();
    window.addEventListener("scroll", sync, true);
    window.addEventListener("resize", sync);
    return () => {
      window.removeEventListener("scroll", sync, true);
      window.removeEventListener("resize", sync);
    };
  }, [open]);

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    function onDown(e) {
      if (triggerRef.current?.contains(e.target) || panelRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // Escape to close
  useEffect(() => {
    if (!open) return;
    function onKey(e) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function select(val) {
    onChange?.({ target: { value: val } });
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        className={cn(
          INPUT_BASE,
          "flex cursor-pointer items-center gap-2 text-left",
          className
        )}
        onClick={() => setOpen((prev) => !prev)}
        {...props}
      >
        <span className="flex-1 truncate">{selectedLabel}</span>
        <ChevronDown
          size={14}
          className={cn(
            "shrink-0 text-muted/50 transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>

      {open &&
        pos &&
        createPortal(
          <div
            ref={panelRef}
            className="soft-scrollbar overflow-y-auto rounded-xl border border-white/10 shadow-2xl backdrop-blur-2xl animate-rise"
            style={{
              ...pos,
              background: "rgba(30, 34, 52, 0.95)",
              maxHeight: "14rem",
            }}
          >
            <div className="p-1">
              {options.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  disabled={opt.disabled}
                  className={cn(
                    "flex w-full items-center rounded-lg px-3 py-2 text-[13px] text-left transition-colors duration-150",
                    String(opt.value) === String(value)
                      ? "bg-teal/10 font-medium text-teal"
                      : "text-muted hover:bg-white/[0.06] hover:text-ink"
                  )}
                  onClick={() => select(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

export function CheckboxInput({ className, type = "checkbox", ...props }) {
  return (
    <label
      className={cn(
        "inline-flex h-5 w-5 shrink-0 cursor-pointer select-none items-center justify-center align-middle",
        className
      )}
    >
      <input
        type={type}
        className="peer sr-only"
        {...props}
      />
      <span
        aria-hidden="true"
        className={cn(
          "pointer-events-none inline-flex h-5 w-5 items-center justify-center rounded-md border-2 border-white/45 bg-panelstrong/80 text-transparent transition-colors",
          "peer-checked:border-teal peer-checked:bg-teal peer-checked:text-shell peer-focus-visible:ring-2 peer-focus-visible:ring-teal/35",
          "peer-disabled:cursor-not-allowed peer-disabled:opacity-60"
        )}
      >
        <svg
          viewBox="0 0 14 14"
          className="h-3 w-3"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 7.5 5.8 10.2 11 4.8" />
        </svg>
      </span>
    </label>
  );
}

export function EmptyState({ title, description, action, className }) {
  return (
    <Card className={cn("glass-card-muted border-dashed text-center", className)}>
      <div className="mx-auto max-w-md space-y-2 py-8">
        <h3 className="text-base font-semibold text-ink/80">{title}</h3>
        <p className="text-[13px] text-muted/60">{description}</p>
        {action ? <div className="flex justify-center pt-2">{action}</div> : null}
      </div>
    </Card>
  );
}

export function LoadingPanel({ label = "Lade Daten..." }) {
  return (
    <Card className="flex min-h-48 items-center justify-center">
      <div className="flex items-center gap-3 text-sm text-muted/70">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/8 border-t-teal/70" />
        {label}
      </div>
    </Card>
  );
}

export function Modal({ open, title, description, onClose, children, footer }) {
  useEffect(() => {
    if (!open) return undefined;

    function handleEscape(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.body.classList.add("overflow-hidden");
    window.addEventListener("keydown", handleEscape);
    return () => {
      document.body.classList.remove("overflow-hidden");
      window.removeEventListener("keydown", handleEscape);
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="glass-overlay fixed inset-0 z-[1000] flex items-center justify-center px-4 py-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="glass-card-strong max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-3xl animate-rise">
        <div className="border-b border-white/6 px-6 py-5">
          <h2 className="text-xl font-semibold text-ink">{title}</h2>
          {description ? <p className="mt-1.5 text-[13px] text-muted/70">{description}</p> : null}
        </div>
        <div className="soft-scrollbar max-h-[calc(90vh-10rem)] overflow-y-auto px-6 py-5">{children}</div>
        {footer ? <div className="border-t border-white/6 px-6 py-4">{footer}</div> : null}
      </div>
    </div>,
    document.body
  );
}

export function ToastViewport({ toasts, onDismiss }) {
  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[1200] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto rounded-xl border px-4 py-3 backdrop-blur-xl animate-rise",
            toast.tone === "danger"
              ? "border-coral/12 bg-coral/8 text-coral"
              : toast.tone === "success"
                ? "border-teal/12 bg-teal/8 text-teal"
                : "border-sky/12 bg-sky/8 text-sky"
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="text-[13px] font-medium">{toast.message}</p>
            <button
              type="button"
              className="shrink-0 rounded-lg p-1 text-current/50 transition hover:bg-white/6 hover:text-current"
              onClick={() => onDismiss(toast.id)}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M3.5 3.5l7 7M10.5 3.5l-7 7" />
              </svg>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
