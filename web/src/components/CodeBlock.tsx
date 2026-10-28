import { useEffect, useRef, useState } from "react";

export interface CodeBlockProps {
  code: string;
  copyLabel: string;
  copiedLabel: string;
  /** Tone of the surface: the hero sits on the paper, install steps on a screen. */
  className?: string;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Clipboard API refused (insecure context, permissions): fall back to a selection.
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

/** A terminal-style snippet with a copy button that confirms what it did. */
export function CodeBlock({ code, copyLabel, copiedLabel, className = "" }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const onCopy = async () => {
    if (!(await copyText(code))) return;
    setCopied(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className={`flex items-start gap-3 rounded-2xl bg-screen px-4 py-3.5 text-screen-ink ${className}`}>
      <pre className="no-scrollbar min-w-0 flex-1 overflow-x-auto font-[inherit] text-[0.9rem] leading-relaxed">
        <code className="font-[inherit]">{code}</code>
      </pre>
      <button
        type="button"
        onClick={() => void onCopy()}
        className="btn btn-screen btn-sm shrink-0"
        aria-live="polite"
      >
        {copied ? copiedLabel : copyLabel}
      </button>
    </div>
  );
}
