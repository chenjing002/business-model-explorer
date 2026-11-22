import type { ReactNode } from "react";
import { AppLink } from "./Navigation";
import { withYear } from "./routes";
import { CONCEPT_BY_ID } from "./knowledge";

export function KnowledgeLink({ concept, year, children }: {
  concept: string | undefined; year: string; children?: ReactNode;
}) {
  const entry = concept ? CONCEPT_BY_ID.get(concept) : undefined;
  if (!entry) return <>{children}</>;
  return <AppLink className="knowledge-link" href={withYear(`/knowledge/${entry.id}`, year)}
    title={`了解${entry.title}`}>{children ?? `了解${entry.title}`}</AppLink>;
}

export function ConceptLinks({ ids, year }: { ids: string[]; year: string }) {
  return <p className="concept-links" aria-label="相关财务概念">
    <span>相关概念：</span>{ids.map((id) => <KnowledgeLink key={id} concept={id} year={year}>
      {CONCEPT_BY_ID.get(id)?.title}
    </KnowledgeLink>)}
  </p>;
}
