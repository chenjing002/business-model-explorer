import entries from "./knowledge/concepts.json";
import links from "./knowledge/links.json";
import { VIEW_PATHS, type View } from "./routes";
import { siteUrl } from "./site";

export interface KnowledgeConcept {
  id: string; title: string; category: string; aliases: string[];
  definition: string; formula: string; interpretation: string;
  convention: string; caveat: string; related: string[]; views: string[]; sources: string[];
}

export const CONCEPTS: KnowledgeConcept[] = entries;
export const CONCEPT_BY_ID = new Map(CONCEPTS.map((entry) => [entry.id, entry]));
export const CATEGORIES = [...new Set(CONCEPTS.map((entry) => entry.category))];
export const VIEW_LABELS: Record<View, string> = {
  home: "好生意榜单", overview: "总览", map: "商业经济地图", tree: "盈利驱动树", capital: "资本与再投资",
  value: "价值创造", valuation: "估值与反向分析", knowledge: "财务知识库", cases: "参考案例",
};
export { VIEW_PATHS };

// These references provide background. The formulas and conventions above
// describe this app's documented pipeline, rather than a generic standard.
export const REFERENCES: Record<string, { label: string; href: string }> = {
  "penman-valuation": {
    label: "Stephen H. Penman，《What Matters in Company Valuation?》（2002，PDF）",
    href: siteUrl("/knowledge/Penman_What_Matters_in_Company_Valuation.pdf"),
  },
  penman: {
    label: "Nissim 与 Penman：比率分析与股权估值（英文研究论文）",
    href: "https://business.columbia.edu/sites/default/files-efs/pubfiles/1063/nissimpenmanratio.pdf",
  },
  "working-capital": {
    label: "ACCA：营运资本管理与现金转换周期（英文）",
    href: "https://www.accaglobal.com/my/en/student/exam-support-resources/fundamentals-exams-study-resources/f9/technical-articles/wcm.html",
  },
  "sec-fcf": {
    label: "美国证监会：非公认会计准则指标，第102.07问（自由现金流定义，英文）",
    href: "https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/non-gaap-financial-measures",
  },
  "amazon-2004-letter": {
    label: "Bezos：亚马逊 2004 年度股东信（自由现金流定义，英文）",
    href: "https://www.sec.gov/Archives/edgar/data/1018724/000119312505070440/dex991.htm",
  },
};

REFERENCES["tushare-units"] = { label: "Tushare：每日指标（总市值为万元、总股本为万股）", href: "https://tushare.pro/document/2?doc_id=32" };
REFERENCES["cas-cashflow"] = { label: "财政部：企业会计准则第31号——现金流量表", href: "https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46250.htm" };

export function conceptFor(kind: keyof typeof links, key: string): string | undefined {
  return (links[kind] as Record<string, string>)[key];
}

export function searchConcepts(query: string, category: string): KnowledgeConcept[] {
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return CONCEPTS.filter((entry) => {
    if (category && entry.category !== category) return false;
    const text = [entry.id, entry.title, ...entry.aliases, entry.definition,
      entry.formula, entry.interpretation, entry.convention, entry.caveat].join(" ").toLocaleLowerCase();
    return terms.every((term) => text.includes(term));
  });
}
