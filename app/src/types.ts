import type { CalculationIndex } from "./calculationDetails";

/** Typed mirror of the pipeline export bundle (schema_version 1).
 *  All financial values are precomputed in Python; null = not disclosed.
 */

export interface ReformulatedBsRow {
  ts_code: string;
  end_date: string; // YYYYMMDD
  oa: number | null;
  fa: number | null;
  ol: number | null;
  fo: number | null;
  noa: number | null;
  nfo: number | null;
  minority_interests: number | null;
  cse_calc: number | null;
  total_assets_reported?: number | null;
  r1_assets_residual: number | null;
  r2_liab_residual: number | null;
  r3_cse_residual: number | null;
}

export interface ReformulatedIsRow {
  ts_code: string;
  end_date: string;
  period_kind: string;
  revenue: number | null;
  total_revenue: number | null;
  oi_core_pretax: number | null;
  unusual_pretax: number | null;
  nfe_pretax: number | null;
  oi_after_tax: number | null;
  oi_core_after_tax: number | null;
  ni_total: number | null;
  ni_parent: number | null;
  r4_pretax_residual: number | null;
}

export interface RatioRow {
  ts_code: string;
  end_date: string;
  basis: "average" | "opening";
  rnoa: number | null;
  opm: number | null;
  opm_core: number | null;
  ato: number | null;
  ollev: number | null;
  flev: number | null;
  nbc: number | null;
  spread: number | null;
  rotce: number | null;
  rotce_direct: number | null;
  roce_parent: number | null;
  gross_margin: number | null;
  ratio_flags: string | null;
  [componentToSales: string]: unknown;
}

export interface WorkingCapitalRow {
  ts_code: string;
  end_date: string;
  dio: number | null;
  dso: number | null;
  dpo: number | null;
  dpo_cogs: number | null;
  ccc: number | null;
  advance_days: number | null;
  /** CCC − 客户预收款天数; absent in bundles exported before it was added. */
  ccc_net_advances?: number | null;
  owc_pct_sales: number | null;
  incr_owc_per_incr_revenue: number | null;
  dpo_method: string | null;
  wc_flags: string | null;
}

export interface CashBridgeStep {
  ts_code: string;
  end_date: string;
  step_order: number;
  concept: string;
  label: string;
  value: number;
  step_kind: "start" | "adjustment" | "total";
}

export interface CashSummaryRow {
  ts_code: string;
  end_date: string;
  ni_total: number | null;
  cfo: number | null;
  capex_paid: number | null;
  fcf_simple: number | null;
  fcf_after_disposals: number | null;
  fcf_simple_def: string | null;
  cash_conversion: number | null;
  cf_flags: string | null;
}

export interface BsComponentRow {
  ts_code: string;
  end_date: string;
  concept: string;
  effective_class: string;
  value: number;
}

export interface EconMapNode {
  ts_code: string;
  end_date: string;
  layer: number;
  layer_name: string;
  node_id: string;
  label: string;
  value: number | null;
  flow_or_stock: "flow" | "stock";
  components_json: string; // [{concept, value}]
  note: string;
  related_json: string; // metric keys into ratios/wc/cash tables
}

export interface EconMapCheck {
  ts_code: string;
  end_date: string;
  layer: number;
  check: string;
  residual: number | null;
}

/** Annual evolution: a Map balance group tracked begin → end. */
export interface EconEvolutionGroup {
  ts_code: string;
  end_date: string;
  side: "sources" | "employment";
  group_id: string; // equals the Map node_id
  label: string;
  panel_id: string; // articulation panel (may span several groups)
  begin_value: number | null;
  end_value: number | null;
  delta: number | null;
  delta_share_of_assets: number | null;
  evo_flags: string | null;
}

/** Articulation bridge step: begin + disclosed flows + inferred residual = end.
 *  `basis` says where the number comes from; inferred_residual is a balancing
 *  item, never a direct-conversion claim. */
export interface EconEvolutionFlow {
  ts_code: string;
  end_date: string;
  side: "sources" | "employment";
  panel_id: string;
  panel_label: string;
  step_order: number;
  concept: string;
  label: string;
  value: number | null;
  step_kind: "start" | "adjustment" | "total";
  basis:
    | "balance"
    | "disclosed_cashflow"
    | "disclosed_supplemental"
    | "disclosed_income"
    | "inferred_residual";
  note: string;
}

export interface EconEvolutionCheck {
  ts_code: string;
  end_date: string;
  check: string;
  residual: number | null;
}

export interface DriverTreeNode {
  ts_code: string;
  end_date: string;
  basis: "average" | "opening";
  node_id: string;
  parent_id: string | null;
  depth: number;
  sort_order: number;
  label: string;
  fmt: "pct" | "x";
  relation: "root" | "identity_term" | "component" | "residual" | "reciprocal" | "context";
  weight: number | null; // sign in parent's additive sum; null = not additive
  value: number | null;
  formula: string;
  related_json: string; // metric keys into other exported tables
  note: string;
  node_flags: string | null;
}

export interface DriverTreeCheck {
  ts_code: string;
  end_date: string;
  basis: "average" | "opening";
  check: string;
  residual: number | null;
}

/** Same shape as CashBridgeStep; NOA_begin → component Δs → NOA_end.
 *  Liability steps are already signed (growth reduces NOA). */
export type CapitalBridgeStep = CashBridgeStep;

export interface CapitalSummaryRow {
  ts_code: string;
  end_date: string;
  noa_begin: number | null;
  noa_end: number | null;
  delta_noa: number | null;
  delta_cse: number | null;
  delta_mi: number | null;
  delta_nfo: number | null;
  revenue: number | null;
  revenue_growth: number | null;
  noa_growth: number | null;
  oi_after_tax: number | null;
  reinvestment_rate: number | null;
  capex_paid: number | null;
  da_total: number | null;
  capex_to_da: number | null;
  fcf_from_oi: number | null;
  fcf_simple: number | null;
  fcf_articulation_diff: number | null;
  fcf_from_oi_def: string | null;
  articulation_note: string | null;
  capex_split_note: string | null;
  cap_flags: string | null;
}

export interface CapitalCheck {
  ts_code: string;
  end_date: string;
  check: string;
  residual: number | null;
}

export interface ResidualIncomeRow {
  ts_code: string;
  end_date: string;
  r_op_assumed: number;
  r_e_assumed: number;
  revenue: number | null;
  oi_after_tax: number | null;
  oi_core_after_tax: number | null;
  ni_parent: number | null;
  oci_total: number | null;
  pm: number | null;
  pm_core: number | null;
  pm_unusual: number | null;
  noa_begin: number | null;
  cse_begin: number | null;
  capital_charge: number | null;
  reoi: number | null;
  reoi_core: number | null;
  rnoa_open: number | null;
  ato_open: number | null;
  spread_op: number | null;
  equity_charge: number | null;
  re_common: number | null;
  roce_open: number | null;
  spread_e: number | null;
  reoi_prev: number | null;
  delta_reoi: number | null;
  reoi_growth: number | null;
  oi_growth: number | null;
  sales_effect: number | null;
  core_margin_effect: number | null;
  unusual_effect: number | null;
  capital_charge_effect: number | null;
  margin_effect: number | null;
  turnover_effect: number | null;
  profitability_effect: number | null;
  growth_effect: number | null;
  bridge_available: boolean;
  drivers_available: boolean;
  rate_note: string | null;
  oci_note: string | null;
  ri_flags: string | null;
}

/** Same shape as CashBridgeStep; ReOI_{t−1} → effects → ReOI_t. */
export type ValueBridgeStep = CashBridgeStep;

export interface RiCheck {
  ts_code: string;
  end_date: string;
  check: string;
  residual: number | null;
}

export interface MarketSnapshotRow {
  ts_code: string;
  end_date: string;
  trade_date: string;
  close: number;
  shares: number;
  market_cap: number;
  pe_reported: number | null;
  pb_reported: number | null;
  dv_ttm_reported: number | null;
  m1_mcap_residual_rel: number | null;
  snapshot_note: string;
}

export interface ValuationRow {
  ts_code: string;
  end_date: string;
  r_op_assumed: number;
  r_e_assumed: number;
  g_assumed: number;
  revenue: number | null;
  oi_after_tax: number | null;
  ni_parent: number | null;
  noa: number | null;
  nfo: number | null;
  minority_interests: number | null;
  cse: number | null;
  noa_begin: number | null;
  cse_begin: number | null;
  reoi_0: number | null;
  re_0: number | null;
  rnoa_0: number | null;
  reoi_1_rnoa: number | null;
  fcf_0: number | null;
  v_noa_book: number | null;
  v_noa_reoi_flat: number | null;
  v_noa_reoi_g: number | null;
  v_noa_rnoa_g: number | null;
  v_equity_book: number | null;
  v_equity_reoi_flat: number | null;
  v_equity_reoi_g: number | null;
  v_equity_rnoa_g: number | null;
  v_equity_ri: number | null;
  v_equity_aeg: number | null;
  earn_1: number | null;
  aeg_2: number | null;
  trade_date: string | null;
  price: number | null;
  shares: number | null;
  market_cap: number | null;
  market_ev: number | null;
  v_per_share: number | null;
  v_to_p: number | null;
  forward_pe_market: number | null;
  forward_pe_model: number | null;
  normal_pe: number | null;
  trailing_pe: number | null;
  implied_g_reoi: number | null;
  implied_g_rnoa: number | null;
  implied_g_fcf: number | null;
  implied_g_equity: number | null;
  implied_r_op: number | null;
  implied_r_e: number | null;
  net_payout_implied: number | null;
  aeg_actual: number | null;
  cum_div_growth: number | null;
  valuation_note: string;
  fcf_note: string;
  val_flags: string | null;
}

/** Same shape as CashBridgeStep; NOA → … → model equity → premium → market cap. */
export type ValuationBridgeStep = CashBridgeStep;

export interface ValuationGridCell {
  ts_code: string;
  end_date: string;
  model: string;
  r: number;
  g: number;
  v_noa: number | null;
  v_equity: number | null;
  v_per_share: number | null;
  v_to_p: number | null;
}

export interface ReverseCurvePoint {
  ts_code: string;
  end_date: string;
  r: number;
  implied_g_reoi: number | null;
  implied_g_rnoa: number | null;
  implied_g_fcf: number | null;
  implied_g_equity: number | null;
}

export interface ValuationCheck {
  ts_code: string;
  end_date: string;
  check: string;
  residual: number | null;
}

interface ReportDisclosure<T> {
  source: string;
  page: number;
  rows: T[];
}

interface ReportAmount {
  source: string;
  page: number;
  value: number | null;
}

export interface OverviewYear {
  end_date: string;
  revenue_yoy: number | null;
  cfo_yoy: number | null;
  rnoa_change: number | null;
  oa_share: number | null;
  fa_share: number | null;
  investment_net_outflow: number | null;
  history?: {
    fcf_per_share: number | null;
    roe: number | null;
    net_margin: number | null;
    asset_turnover: number | null;
    equity_multiplier: number | null;
  };
  disclosure: {
    report_url: string;
    products: ReportDisclosure<{ label: string; revenue: number | null; gross_margin: number | null }> | null;
    inventory: ReportDisclosure<{ label: string; begin: number | null; end: number | null; delta: number | null }> | null;
    cash_explanation: { source: string; page: number; text: string } | null;
    shareholder_distribution: ReportAmount | null;
    share_repurchase: ReportAmount | null;
  } | null;
}

export interface Bundle {
  schema_version: number;
  ts_code: string;
  exported_at: string;
  unit: string;
  conventions: Record<string, string>;
  overview?: { company_name: string | null; years: OverviewYear[] };
  calculation_details?: CalculationIndex;
  reformulated_bs: ReformulatedBsRow[];
  reformulated_is: ReformulatedIsRow[];
  ratios: RatioRow[];
  working_capital: WorkingCapitalRow[];
  cash_bridge: CashBridgeStep[];
  cash_summary: CashSummaryRow[];
  bs_components: BsComponentRow[];
  reclass_decisions: unknown[];
  econ_map_nodes: EconMapNode[];
  econ_map_checks: EconMapCheck[];
  econ_evolution_groups: EconEvolutionGroup[];
  econ_evolution_flows: EconEvolutionFlow[];
  econ_evolution_checks: EconEvolutionCheck[];
  driver_tree_nodes: DriverTreeNode[];
  driver_tree_checks: DriverTreeCheck[];
  capital_bridge: CapitalBridgeStep[];
  capital_summary: CapitalSummaryRow[];
  capital_checks: CapitalCheck[];
  residual_income: ResidualIncomeRow[];
  value_bridge: ValueBridgeStep[];
  ri_checks: RiCheck[];
  market_snapshot: MarketSnapshotRow[];
  valuation: ValuationRow[];
  valuation_bridge: ValuationBridgeStep[];
  valuation_grid: ValuationGridCell[];
  valuation_curve: ReverseCurvePoint[];
  valuation_checks: ValuationCheck[];
}
