import { createContext, useContext, type AnchorHTMLAttributes } from "react";
import { withCompany } from "./routes";
import { siteUrl } from "./site";

export const NavigationContext = createContext<(href: string) => void>(() => {});
export const CompanyContext = createContext("");

/** Real anchors retain open-in-new-tab, copying and keyboard behavior.
 *  `href` is a site path; the anchor carries the deployed URL. */
export function AppLink({ href = "/", onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) {
  const navigate = useContext(NavigationContext);
  const url = withCompany(href, useContext(CompanyContext));
  return <a {...props} href={siteUrl(url)} onClick={(event) => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
        event.shiftKey || event.altKey || props.target || props.download) return;
    event.preventDefault();
    navigate(url);
  }} />;
}
