import { memo, useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { availability, industryOf, searchCompanies, type CompanyEntry, type CompanyIndex } from "./companies";

const Option = memo(function Option({ entry, position, id, active, current, unavailable, onHover, onPick }: {
  entry: CompanyEntry; position: number; id: string; active: boolean; current: boolean;
  unavailable: { tag: string; text: string } | null;
  onHover: (position: number) => void; onPick: (code: string) => void;
}) {
  return <li id={id} role="option" aria-selected={active} aria-current={current || undefined}
    className={`picker__option${active ? " picker__option--active" : ""}${unavailable ? " picker__option--raw" : ""}`}
    title={unavailable ? `暂无分析：${unavailable.text}` : undefined}
    onMouseMove={() => onHover(position)} onMouseDown={(event) => event.preventDefault()}
    onClick={() => onPick(entry.ts_code)}>
    <span className="picker__name">{entry.name ?? "名称未披露"}</span>
    <span className="picker__code">{entry.ts_code}</span>
    {current ? <span className="picker__tag picker__tag--current">当前</span> :
      unavailable && <span className="picker__tag picker__tag--raw">{unavailable.tag}</span>}
  </li>;
});

/** Company search: name, code, pinyin initials or industry; results grouped by
 *  industry. ↑/↓ move, PgUp/PgDn jump between industries, Enter opens. */
export function CompanyPicker({ index, error, current, currentName, onSelect }: {
  index: CompanyIndex | null; error: string | null; current: string; currentName?: string | null;
  onSelect: (code: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const baseId = useId();
  const listId = `${baseId}-list`;
  const optionId = (code: string) => `${baseId}-${code}`;

  const groups = useMemo(() => open && index ? searchCompanies(index, query, current) : [],
    [open, index, query, current]);
  const flat = useMemo(() => groups.flatMap((group) => group.companies), [groups]);
  const groupStarts = useMemo(() => {
    const starts: number[] = [];
    groups.reduce((offset, group) => { starts.push(offset); return offset + group.companies.length; }, 0);
    return starts;
  }, [groups]);
  // One stable object per company, so memoized rows skip re-rendering on ↑/↓.
  const unavailable = useMemo(() => new Map(index?.companies.map((company) =>
    [company.ts_code, availability(index, company.ts_code)]) ?? []), [index]);
  const flatRef = useRef(flat);
  flatRef.current = flat;

  const entry = index?.byCode.get(current);
  const label = currentName || entry?.name || current;

  const close = (refocus: boolean) => {
    setOpen(false);
    setQuery("");
    if (refocus) trigger.current?.focus();
  };
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const pick = useCallback((code: string) => {
    setOpen(false);
    setQuery("");
    trigger.current?.focus();
    if (code !== current) selectRef.current(code);
  }, [current]);
  const hover = useCallback((position: number) => setActive(position), []);

  useEffect(() => { if (open) input.current?.focus(); }, [open]);
  // Without a query the list opens on the current company, so ↑/↓ step through
  // its industry peers; a query starts from the best match.
  useEffect(() => {
    if (!open) return;
    const at = query.trim() ? 0 : flatRef.current.findIndex((company) => company.ts_code === current);
    setActive(Math.max(at, 0));
  }, [open, index, current, query]);
  useEffect(() => {
    const code = flat[active]?.ts_code;
    if (open && code) document.getElementById(optionId(code))?.scrollIntoView({ block: "nearest" });
  }, [open, active, flat]);
  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) close(false);
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [open]);

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const count = flat.length;
    const groupOf = (position: number) => {
      let g = 0;
      while (g + 1 < groupStarts.length && groupStarts[g + 1] <= position) g += 1;
      return g;
    };
    if (event.key === "Escape") { event.preventDefault(); close(true); return; }
    if (event.key === "Tab") { close(false); return; }
    if (!count) return;
    let next: number | null = null;
    if (event.key === "ArrowDown") next = (active + 1) % count;
    else if (event.key === "ArrowUp") next = (active - 1 + count) % count;
    else if (event.key === "PageDown") next = groupStarts[Math.min(groupOf(active) + 1, groupStarts.length - 1)];
    else if (event.key === "PageUp") {
      const g = groupOf(active);
      next = groupStarts[active === groupStarts[g] ? Math.max(g - 1, 0) : g];
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (flat[active]) pick(flat[active].ts_code);
      return;
    }
    if (next !== null) { event.preventDefault(); setActive(next); }
  };

  const total = index?.companies.length ?? 0;
  let position = 0;
  return <div className="picker" ref={root}>
    <button ref={trigger} type="button" className="picker__trigger" aria-haspopup="dialog" aria-expanded={open}
      title="切换公司（页面上按 ← → 切换上一家 / 下一家已分析公司，按行业顺序）" onClick={() => open ? close(false) : setOpen(true)}
      onKeyDown={(event) => {
        if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) { event.preventDefault(); setOpen(true); }
      }}>
      <span className="picker__current">{label}</span>
      <span className="picker__meta">{current}{entry ? ` · ${industryOf(entry)}` : ""}</span>
      <svg className="picker__chevron" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <path d="m3 4.5 3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </button>
    {open && <div className="picker__panel" role="dialog" aria-label="切换公司">
      <input ref={input} className="picker__search" type="search" role="combobox" value={query}
        placeholder="搜索公司名称、代码、拼音首字母或行业" aria-expanded="true" aria-controls={listId}
        aria-autocomplete="list" aria-activedescendant={flat[active] ? optionId(flat[active].ts_code) : undefined}
        onChange={(event) => setQuery(event.target.value)} onKeyDown={onKeyDown} />
      <p className="picker__count" role="status">
        {error ? `公司列表加载失败：${error}` : !index ? "正在加载公司列表…" :
          query.trim() ? `找到 ${flat.length.toLocaleString("zh-CN")} 家 · ${groups.length} 个行业` :
          `共 ${total.toLocaleString("zh-CN")} 家 · ${groups.length} 个行业 · 已分析 ${index.analyzed.size.toLocaleString("zh-CN")} 家（标签注明未分析原因）`}
      </p>
      {index && <ul id={listId} className="picker__list" role="listbox" aria-label="公司（按行业分组）">
        {groups.map((group) => {
          const headingId = `${baseId}-g-${group.industry}`;
          return <li key={group.industry} role="presentation">
            <div id={headingId} className="picker__group">{group.industry}<span>{group.companies.length} 家</span></div>
            <ul role="group" aria-labelledby={headingId}>
              {group.companies.map((company) => {
                const at = position++;
                return <Option key={company.ts_code} entry={company} position={at} id={optionId(company.ts_code)}
                  active={at === active} current={company.ts_code === current}
                  unavailable={unavailable.get(company.ts_code) ?? null} onHover={hover} onPick={pick} />;
              })}
            </ul>
          </li>;
        })}
        {flat.length === 0 && <li role="presentation" className="picker__empty">没有匹配“{query.trim()}”的公司</li>}
      </ul>}
      <p className="picker__hint" aria-hidden="true">
        <kbd>↑</kbd><kbd>↓</kbd> 选择 · <kbd>PgUp</kbd><kbd>PgDn</kbd> 切换行业 · <kbd>Enter</kbd> 打开 · <kbd>Esc</kbd> 关闭
      </p>
    </div>}
  </div>;
}
