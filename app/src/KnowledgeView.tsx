import { useEffect, useMemo, useRef, useState } from "react";
import { AppLink } from "./Navigation";
import { ArticulationDiagram, showsArticulation } from "./ArticulationDiagram";
import { KnowledgeLink } from "./KnowledgeLink";
import { CATEGORIES, CONCEPTS, CONCEPT_BY_ID, REFERENCES, searchConcepts, VIEW_LABELS } from "./knowledge";
import { VIEW_PATHS, withYear, type View } from "./routes";

export function KnowledgeView({ concept, year }: { concept: string; year: string }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const results = useMemo(() => searchConcepts(query, category), [query, category]);
  const entry = CONCEPT_BY_ID.get(concept || "penman-valuation");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    // On narrow screens the article follows the index; bring a deep-linked
    // heading into view while leaving the knowledge home at its search field.
    if (concept) heading.current?.focus();
  }, [concept]);

  return <main className="knowledge">
    <div className="knowledge__intro">
      <p className="knowledge__eyebrow">财务知识库</p>
      <h2>佩曼估值与财务分析</h2>
      <p>以 Stephen H. Penman 的估值论文为基础，查阅报表勾稽、指标公式与本项目采用的假设。</p>
      <a href={REFERENCES["penman-valuation"].href} target="_blank" rel="noreferrer">阅读 Penman 论文原文（PDF）</a>
    </div>
    <div className="knowledge__layout">
      <aside className="knowledge__index" aria-label="查找财务概念">
        <label htmlFor="concept-search">搜索 {CONCEPTS.length} 个概念</label>
        <input id="concept-search" type="search" value={query} placeholder="试试“净经营资产”、RNOA 或营运资本"
          onChange={(event) => setQuery(event.target.value)} />
        <label htmlFor="concept-category">主题</label>
        <select id="concept-category" value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">全部主题</option>
          {CATEGORIES.map((name) => <option key={name}>{name}</option>)}
        </select>
        <p className="knowledge__count" role="status">找到 {results.length} 个概念</p>
        {results.length === 0 && <div className="knowledge__empty">
          <p>未找到匹配概念，请尝试英文缩写、更宽泛的词语或其他主题。</p>
          <button onClick={() => { setQuery(""); setCategory(""); }}>清除筛选</button>
        </div>}
        <nav className="knowledge__results" aria-label="财务知识库">
          {results.map((item) => <AppLink key={item.id} href={withYear(`/knowledge/${item.id}`, year)}
            className={`knowledge__result ${item.id === entry?.id ? "knowledge__result--active" : ""}`}
            aria-current={item.id === entry?.id ? "page" : undefined}>
            <span>{item.title}</span><small>{item.category}</small>
          </AppLink>)}
        </nav>
      </aside>
      {entry ? <article className="knowledge__article" aria-labelledby="concept-title">
        <header>
          <p className="knowledge__eyebrow">{entry.category}</p>
          <h2 id="concept-title" ref={heading} tabIndex={-1}>{entry.title}</h2>
          <p className="knowledge__definition">{entry.definition}</p>
        </header>
        <section aria-label="计算公式" className="knowledge__formula">{entry.formula}</section>
        {showsArticulation(entry.id) && <section>
          <h3>三张报表如何勾稽（重构口径）</h3>
          <ArticulationDiagram />
        </section>}
        <section><h3>如何解读</h3><p>{entry.interpretation}</p></section>
        <section><h3>本网站口径</h3><p>{entry.convention}</p></section>
        <section className="knowledge__caveat"><h3>注意事项</h3><p>{entry.caveat}</p></section>
        <section>
          <h3>相关概念</h3>
          <div className="knowledge__related">{entry.related.map((id) =>
            <KnowledgeLink key={id} concept={id} year={year}>{CONCEPT_BY_ID.get(id)?.title}</KnowledgeLink>)}
          </div>
        </section>
        <section><h3>在分析页面中查看</h3>
          <div className="knowledge__related">{entry.views.map((key) =>
            <AppLink key={key} href={withYear(VIEW_PATHS[key as View], year)}>{VIEW_LABELS[key as View]}</AppLink>)}
          </div>
        </section>
        {entry.sources.length > 0 && <section className="knowledge__sources"><h3>资料来源</h3>
          {entry.sources.map((id) => <a key={id} href={REFERENCES[id].href} target="_blank" rel="noreferrer">
            {REFERENCES[id].label}</a>)}
        </section>}
      </article> : <article className="knowledge__article">
        <h2 id="concept-title" ref={heading} tabIndex={-1}>未找到该概念</h2>
        <p>此链接未对应已收录的概念，请搜索目录或返回知识库首页。</p>
        <AppLink href={withYear("/knowledge", year)}>浏览财务知识库</AppLink>
      </article>}
    </div>
    <p className="knowledge__method">公式对应年度合并财报分析；期初与平均资本分别标注。金额默认以亿元显示，股价以元/股显示。
      模型假设、报表披露与会计恒等式含义不同，请结合每个条目的口径和注意事项阅读。</p>
  </main>;
}
