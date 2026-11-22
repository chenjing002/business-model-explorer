import { useEffect, useRef } from "react";
import { MoutaiCase } from "./MoutaiCase";
import { AppLink } from "./Navigation";
import { CASES } from "./referenceCases";
import { withYear } from "./routes";
import type { Bundle } from "./types";

export function ReferenceCasesContent({ caseId, year, bundle = null, bundleError = null }: {
  caseId: string; year: string; bundle?: Bundle | null; bundleError?: string | null;
}) {
  const selected = CASES.find((c) => c.id === (caseId || CASES[0].id));
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [caseId]);
  return <main className="cases">
    <div className="cases__intro">
      <p className="cases__eyebrow">参考案例 · 从概念到经济机制</p>
      <h2 ref={heading} tabIndex={-1}>一家公司的商业实质怎么读？</h2>
      <p>以贵州茅台（600519.SH）为样本，沿六个分析页面逐步识别生意的回报、资本与定价。所有数字来自公司数据包，金额按人民币亿元展示。</p>
    </div>
    <nav className="cases__nav" aria-label="参考案例选择">{CASES.map((c) => <AppLink key={c.id}
      href={withYear(`/cases/${c.id}`, year)} aria-current={selected?.id === c.id ? "page" : undefined}>
      {c.title}</AppLink>)}</nav>
    {selected ? <MoutaiCase bundle={bundle} error={bundleError} year={year} /> :
      <section className="panel cases__section"><h3>未找到该参考案例</h3>
        <AppLink href={withYear("/cases", year)}>浏览参考案例</AppLink></section>}
  </main>;
}

export function ReferenceCasesView(props: {
  caseId: string; year: string; bundle?: Bundle | null; bundleError?: string | null;
}) {
  return <ReferenceCasesContent {...props} />;
}
