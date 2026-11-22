import { useMemo } from "react";
import { ConceptLinks } from "./KnowledgeLink";
import { DriverEffectsChart } from "./charts/DriverEffectsChart";
import { ResidualChart } from "./charts/ResidualChart";
import { SpreadChart } from "./charts/SpreadChart";
import { WaterfallChart } from "./charts/WaterfallChart";
import { yearOf } from "./data";
import type { Bundle } from "./types";

/** Module 11 — Growth quality & residual income. All values precomputed in
 *  Python (residual_income / value_bridge); this view only renders. */
export function ValueView({ bundle, year }: { bundle: Bundle; year: string }) {
  const steps = useMemo(
    () => bundle.value_bridge.filter((s) => yearOf(s.end_date) === year),
    [bundle, year],
  );
  const row = useMemo(
    () => bundle.residual_income.find((r) => yearOf(r.end_date) === year),
    [bundle, year],
  );
  const flags = row?.ri_flags ?? "";
  const rates = row
    ? `经营必要报酬率 ${(row.r_op_assumed * 100).toFixed(1)}%，权益必要报酬率 ${(row.r_e_assumed * 100).toFixed(1)}%`
    : "";

  return (
    <main className="grid">
      <section className="panel">
        <h2>剩余经营收益变动桥，{year}年（亿元）</h2>
        <p className="panel__note">
          上期剩余经营收益，加上收入增长、核心利润率和特殊项目的影响，再扣除新增资本的资本费用，得到本期剩余经营收益；分解采用收入优先顺序。
          {flags && <span className="flag"> 提示：{flags}</span>}
        </p>
        {steps.length > 0 ? (
          <WaterfallChart steps={steps} table="value_bridge" />
        ) : (
          <p className="panel__note">{year}年无法构造变动桥：需连续两年的期初资本与收入数据{flags ? "，具体原因见上方提示" : ""}。</p>
        )}
        <ConceptLinks ids={["reoi", "reinvestment"]} year={year} />
      </section>

      <section className="panel">
        <h2>剩余收益（{rates}，均为假设）</h2>
        <p className="panel__note">
          剩余经营收益（ReOI）＝税后经营收益－r_op×期初净经营资产；剩余权益收益（RE）＝归母综合收益－r_e×期初归母权益。{" "}
          {row?.rate_note ?? "必要报酬率属于假设，并非估计值。"}{" "}
          {row?.oci_note ?? ""}
        </p>
        <ResidualChart rows={bundle.residual_income} />
        <ConceptLinks ids={["reoi", "equity-re", "required-return"]} year={year} />
      </section>

      <section className="panel">
        <h2>超过必要报酬率的收益率差（百分点）</h2>
        <p className="panel__note">
          分别展示期初资本口径的经营、归母权益收益率减去假设必要报酬率的差额。两条线的差异与融资贡献及少数股东权益有关。
        </p>
        <SpreadChart rows={bundle.residual_income} />
        <ConceptLinks ids={["rnoa", "roce", "required-return"]} year={year} />
      </section>

      <section className="panel">
        <h2>剩余经营收益变动：利润率、周转与资本增长（亿元）</h2>
        <p className="panel__note">
          ReOI＝（RNOA－r）×期初NOA。增长效应按上期收益率差衡量新增资本；若新增资本未带来收入，周转效应会抵减该贡献，需将两者一起阅读。仅展示RNOA适用的年份。
        </p>
        <DriverEffectsChart rows={bundle.residual_income} />
        <ConceptLinks ids={["reoi", "ato"]} year={year} />
      </section>
    </main>
  );
}
