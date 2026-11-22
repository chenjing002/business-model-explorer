import { createContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { auditTarget, calculationHtml, type CalculationIndex } from "./calculationDetails";

export const CalculationContext = createContext<CalculationIndex | undefined>(undefined);

export function AuditValue({ year, code, children }: { year: string; code: string; children: ReactNode }) {
  return <button type="button" className="calc-value" {...auditTarget(year, code)}>{children}</button>;
}

export function CalculationProvider({ index, children }: { index?: CalculationIndex; children: ReactNode }) {
  const [active, setActive] = useState<HTMLElement | null>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!index) return;
    let close: number | undefined;
    const inside = (node: EventTarget | null) => node instanceof Node && panel.current?.contains(node);
    const targetOf = (node: EventTarget | null) => node instanceof Element
      ? node.closest<HTMLElement>("[data-calculation]") : null;
    const show = (event: Event) => {
      if (inside(event.target)) {
        window.clearTimeout(close);
        return;
      }
      const node = targetOf(event.target);
      if (!node) return;
      window.clearTimeout(close);
      setActive(node);
    };
    const hide = (event: PointerEvent | FocusEvent) => {
      if (!inside(event.target) && !targetOf(event.target)) return;
      if (inside(event.relatedTarget) || targetOf(event.target) === targetOf(event.relatedTarget) && !inside(event.target)) return;
      window.clearTimeout(close);
      close = window.setTimeout(() => setActive(null), 180);
    };
    const dismiss = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.type === "scroll" && inside(event.target)) return;
      setActive(null);
    };
    const outside = (event: PointerEvent) => {
      if (!inside(event.target) && !targetOf(event.target)) setActive(null);
    };
    document.addEventListener("pointerover", show);
    document.addEventListener("pointerout", hide);
    document.addEventListener("focusin", show);
    document.addEventListener("focusout", hide);
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", dismiss);
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", dismiss, true);
    return () => {
      window.clearTimeout(close);
      document.removeEventListener("pointerover", show);
      document.removeEventListener("pointerout", hide);
      document.removeEventListener("focusin", show);
      document.removeEventListener("focusout", hide);
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", dismiss);
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", dismiss, true);
    };
  }, [index]);

  const [date, code] = active?.dataset.calculation?.split(" ") ?? [];
  const html = index && active?.isConnected ? calculationHtml(index, date, code) : "";
  useEffect(() => {
    if (!panel.current || !active || !html) return;
    const box = active.getBoundingClientRect();
    const popover = panel.current;
    popover.style.left = `${Math.max(8, Math.min(box.left, window.innerWidth - popover.offsetWidth - 8))}px`;
    const below = box.bottom + 4;
    const above = box.top - popover.offsetHeight - 4;
    popover.style.top = `${above >= 8 && below + popover.offsetHeight > window.innerHeight - 8 ? above : Math.max(8, Math.min(below, window.innerHeight - popover.offsetHeight - 8))}px`;
    active.setAttribute("aria-describedby", "calculation-popover");
    return () => { active.removeAttribute("aria-describedby"); };
  }, [active, html]);

  return <CalculationContext.Provider value={index}>
    {children}
    {html && createPortal(<div id="calculation-popover" ref={panel}
      className="calc-panel calc-panel--floating" tabIndex={0} aria-label="原始计算项"
      dangerouslySetInnerHTML={{ __html: `<header>${date.slice(0, 4)} 年 · 原始计算项</header>${html}` }} />,
      document.body)}
  </CalculationContext.Provider>;
}
