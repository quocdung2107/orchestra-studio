import { createContext, useContext, useState, type ReactNode } from "react";

export type View = "overview" | "agents" | "runs" | "organization" | "capabilities" | "approvals" | "knowledge" | "analytics" | "connections";
export type Selection = { kind: "agent"; id: string } | { kind: "run"; id: string } | null;

type Ctx = {
  companyId: string | null;
  setCompanyId: (id: string | null) => void;
  view: View;
  setView: (v: View) => void;
  selection: Selection;
  select: (s: Selection) => void;
};

const SelectionContext = createContext<Ctx | null>(null);

const LAST_COMPANY = "orchestra.lastCompany";

function readLast(): string | null {
  try {
    return localStorage.getItem(LAST_COMPANY);
  } catch {
    return null;
  }
}

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [companyId, setCompany] = useState<string | null>(readLast);
  const [view, setView] = useState<View>("overview");
  const [selection, select] = useState<Selection>(null);

  const setCompanyId = (id: string | null) => {
    setCompany(id);
    select(null);
    try {
      if (id) localStorage.setItem(LAST_COMPANY, id);
      else localStorage.removeItem(LAST_COMPANY);
    } catch {
      /* UI preference only */
    }
  };

  return (
    <SelectionContext.Provider value={{ companyId, setCompanyId, view, setView, selection, select }}>
      {children}
    </SelectionContext.Provider>
  );
}

export function useSelection(): Ctx {
  const ctx = useContext(SelectionContext);
  if (!ctx) throw new Error("useSelection outside SelectionProvider");
  return ctx;
}
