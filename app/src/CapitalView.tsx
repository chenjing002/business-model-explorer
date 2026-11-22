import { useMemo } from "react";
import { ConceptLinks } from "./KnowledgeLink";
import { CapexDaChart } from "./charts/CapexDaChart";
import { FcfChart } from "./charts/FcfChart";
import { GrowthChart } from "./charts/GrowthChart";
import { WaterfallChart } from "./charts/WaterfallChart";
import { yearOf } from "./data";
import type { Bundle } from "./types";

/** Module 10 — Capital employed & reinvestment. All values precomputed in
 *  Python (capital_bridge / capital_summary); this view only renders. */
export function CapitalView({ bundle, year }: { bundle: Bundle; year: string }) {
  const steps = useMemo(
    () => bundle.capital_bridge.filter((s) => yearOf(s.end_date) === year),
    [bundle, year],
  );
  const row = useMemo(
    () => bundle.capital_summary.find((r) => yearOf(r.end_date) === year),
    [bundle, year],
  );
  const flags = row?.cap_flags ?? "";

  return (
    <main className="grid">
      <section className="panel">
        <h2>经营资本变动桥，{year}年（亿元）</h2>
        <p className="panel__note">
          期初净经营资产加上各构成项变动，得到期末净经营资产。供应商信用、客户预收款等经营负债增加时，减少净资本占用；“其他”项列示剩余构成。
          {flags && <span className="flag"> 提示：{flags}</span>}
        </p>
        {steps.length > 0 ? (
          <WaterfallChart steps={steps} table="capital_bridge" />
        ) : (
          <p className="panel__note">{year}年缺少期初余额，无法构造资本变动桥。</p>
        )}
        <ConceptLinks ids={["noa", "reinvestment"]} year={year} />
      </section>

      <section className="panel">
        <h2>收入增长、资本增长与再投资率</h2>
        <p className="panel__note">
          正资本基数下，净经营资产增长快于收入会降低周转率。再投资率＝净经营资产增加额／税后经营收益；断点表示计算受限或缺少期初数据。
        </p>
        <GrowthChart summary={bundle.capital_summary} />
        <ConceptLinks ids={["reinvestment", "ato"]} year={year} />
      </section>

      <section className="panel">
        <h2>资本开支与折旧摊销（亿元）</h2>
        <p className="panel__note">
          {row?.capex_split_note ??
            "仅凭汇总财报无法区分维持性与增长性资本开支。"}
        </p>
        <CapexDaChart summary={bundle.capital_summary} />
        <ConceptLinks ids={["capex"]} year={year} />
      </section>

      <section className="panel">
        <h2>两种自由现金流口径（亿元）</h2>
        <p className="panel__note">
          重构口径为税后经营收益减净经营资产增加额；简式口径为经营现金流量净额减资本开支。两者差异可能来自现金流分类、其他权益变动及计量时点，差额如实列示。
        </p>
        <FcfChart summary={bundle.capital_summary} />
        <ConceptLinks ids={["fcf", "cfo"]} year={year} />
      </section>
    </main>
  );
}
