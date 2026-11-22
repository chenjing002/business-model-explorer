import { useMemo } from "react";
import { formatAmount, formatPrice, formatResidual } from "./format";
import { AuditValue } from "./CalculationPopover";
import { ConceptLinks } from "./KnowledgeLink";
import { ImpliedGrowthChart } from "./charts/ImpliedGrowthChart";
import { ModelVsMarketChart } from "./charts/ModelVsMarketChart";
import { PeChart } from "./charts/PeChart";
import { ReverseCurveChart } from "./charts/ReverseCurveChart";
import { SensitivityHeatmap } from "./charts/SensitivityHeatmap";
import { WaterfallChart } from "./charts/WaterfallChart";
import { yearOf } from "./data";
import type { Bundle, ValuationRow } from "./types";

const pct = (v: number | null, dp = 1) => (v == null ? "—" : `${(v * 100).toFixed(dp)}%`);
const money = (v: number | null) => formatAmount(v);
const num = (v: number | null, dp = 2) => (v == null ? "—" : v.toFixed(dp));

/** Module 12 — Valuation & reverse analysis. Every number is precomputed in
 *  Python (valuation_* tables); this view only filters and renders. */
export function ValuationView({ bundle, year }: { bundle: Bundle; year: string }) {
  const row = useMemo<ValuationRow | undefined>(
    () => bundle.valuation.find((r) => yearOf(r.end_date) === year),
    [bundle, year],
  );
  const steps = useMemo(
    () => bundle.valuation_bridge.filter((s) => yearOf(s.end_date) === year),
    [bundle, year],
  );
  const cells = useMemo(
    () => bundle.valuation_grid.filter((c) => yearOf(c.end_date) === year),
    [bundle, year],
  );
  const curve = useMemo(
    () => bundle.valuation_curve.filter((c) => yearOf(c.end_date) === year),
    [bundle, year],
  );
  const checks = useMemo(() => {
    const ys = bundle.valuation_checks.filter((c) => yearOf(c.end_date) === year);
    const money = ys.filter((c) => !c.check.startsWith("M"));
    const maxAbs = money.reduce((m, c) => Math.max(m, Math.abs(c.residual ?? 0)), 0);
    return { n: ys.length, maxAbs };
  }, [bundle, year]);

  const rates = row
    ? `r_op ${pct(row.r_op_assumed)}，r_e ${pct(row.r_e_assumed)}，g ${pct(row.g_assumed)}`
    : "";
  const flags = row?.val_flags ?? "";
  // No year-end price in any year (e.g. listed after the latest year end):
  // market-implied charts would be empty frames.
  const hasMarket = bundle.valuation.some((r) => r.market_cap != null);
  const noMarket = <p className="panel__note">该公司在已披露年度均无年末行情（例如在最近一个年末之后才上市），无法反推价格隐含参数；模型价值仍按账面与剩余收益计算。</p>;

  return (
    <main className="grid">
      <section className="panel">
        <h2>估值变动桥，{year}年（{rates}，均为假设；金额：亿元）</h2>
        <p className="panel__note">
          从账面净经营资产出发，加上零增长剩余经营收益现值与按g增长的额外价值，再计入账面净金融资产、扣除少数股东权益，得到模型股权价值。末项为市场相对模型的溢价或折价。
          {flags && <span className="flag"> 提示：{flags}</span>}
        </p>
        {steps.length > 0 ? (
          <WaterfallChart steps={steps} table="valuation_bridge" />
        ) : (
          <p className="panel__note">{year}年无法构造估值桥，需有期初余额、行情数据且g＜r。</p>
        )}
        {row && (
          <table className="inspector__table">
            <tbody>
              <tr><td>收盘价（{row.trade_date ?? "—"}）／模型每股价值</td><td className="num"><AuditValue year={year} code="price">{formatPrice(row.price)}</AuditValue>／<AuditValue year={year} code="v_per_share">{formatPrice(row.v_per_share)}</AuditValue></td></tr>
              <tr><td>模型价值／总市值（V/P，倍）</td><td className="num"><AuditValue year={year} code="v_to_p">{num(row.v_to_p)}</AuditValue></td></tr>
              <tr><td>隐含永续增长率g（ReOI基数），r_op＝ {pct(row.r_op_assumed)}</td><td className="num"><AuditValue year={year} code="implied_g_reoi">{pct(row.implied_g_reoi, 2)}</AuditValue></td></tr>
              <tr><td>隐含经营必要报酬率r_op，g＝ {pct(row.g_assumed)}</td><td className="num"><AuditValue year={year} code="implied_r_op">{pct(row.implied_r_op, 2)}</AuditValue></td></tr>
              <tr><td>剩余权益收益估值／AEG估值（亿元）</td><td className="num"><AuditValue year={year} code="v_equity_ri">{money(row.v_equity_ri)}</AuditValue>／<AuditValue year={year} code="v_equity_aeg">{money(row.v_equity_aeg)}</AuditValue></td></tr>
              <tr><td>本年校验项数（金额最大绝对差额，元）</td><td className="num">{checks.n}项（{formatResidual(checks.maxAbs)}）</td></tr>
            </tbody>
          </table>
        )}
        <ConceptLinks ids={["valuation", "reoi"]} year={year} />
      </section>

      <section className="panel">
        <h2>参数敏感性，{year}年：模型价值／总市值（倍）</h2>
        <p className="panel__note">
          展示必要报酬率与永续增长率组合下的估值倍数，每个r均重新计算资本费用。描边单元格为当前假设，应结合整个区间理解参数影响。
        </p>
        {cells.length > 0 ? (
          <SensitivityHeatmap cells={cells} assumed={row ? { r: row.r_op_assumed, g: row.g_assumed } : null} />
        ) : (
          <p className="panel__note">{year}年缺少期初余额或行情数据，无法展示敏感性矩阵。</p>
        )}
        <ConceptLinks ids={["required-return", "reverse-valuation"]} year={year} />
      </section>

      <section className="panel">
        <h2>模型股权价值与总市值（亿元）</h2>
        <p className="panel__note">
          实线为年末总市值，虚线为假设模型价值。同年年末股价搭配数月后才披露的年报属于事后分析，不能直接作为当时可交易的信号。
        </p>
        <ModelVsMarketChart rows={bundle.valuation} />
        <ConceptLinks ids={["valuation", "nfo"]} year={year} />
      </section>

      <section className="panel">
        <h2>价格隐含的永续增长率（给定必要报酬率）</h2>
        <p className="panel__note">
          隐含参数均反算验证回到市场价值。{row?.fcf_note ?? ""}
          表格另列给定增长率 g 时的隐含必要报酬率。
        </p>
        {hasMarket ? <ImpliedGrowthChart rows={bundle.valuation} /> : noMarket}
        <ConceptLinks ids={["reverse-valuation"]} year={year} />
      </section>

      <section className="panel">
        <h2>反向估值曲线，{year}年：与价格一致的r、g组合</h2>
        <p className="panel__note">
          曲线上每点对应的模型价值等于年末市值。更高必要报酬率通常需要更高增长率；断点表示该基数下不存在适用的永续解。
        </p>
        {curve.length > 0 ? (
          <ReverseCurveChart points={curve} rAssumed={row?.r_op_assumed ?? null} />
        ) : (
          <p className="panel__note">{year}年没有可用的反向估值曲线。</p>
        )}
        <ConceptLinks ids={["reverse-valuation", "required-return"]} year={year} />
      </section>

      <section className="panel">
        <h2>收益倍数与异常盈利增长（AEG）</h2>
        <p className="panel__note">
          正常前瞻倍数＝1／r_e。前瞻倍数以模型预测的归母综合收益为分母，同年市盈率以归母净利润为分母。前瞻综合收益＝r_e×期末归母权益＋RE₀×（1＋g）。
        </p>
        <PeChart rows={bundle.valuation} />
        <ConceptLinks ids={["aeg", "equity-re"]} year={year} />
      </section>

      {row && <p className="panel__note" style={{ gridColumn: "1 / -1" }}>{row.valuation_note}</p>}
    </main>
  );
}
