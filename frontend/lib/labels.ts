// Human-readable labels for the UI. Internal identifiers (snake_case / short
// codes) must never be shown to users — always map through here.

export function humanize(s: string): string {
  if (!s) return s;
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const CATEGORY: Record<string, string> = {
  // risk categories
  payment: "Payment terms",
  escalation: "Price escalation",
  ld: "Liquidated damages",
  emd: "EMD / security",
  termination: "Termination",
  ground_conditions: "Ground conditions",
  arbitration: "Arbitration",
  // BOQ defect categories
  arith: "Arithmetic error",
  blank_rate: "Blank rate",
  duplicate: "Duplicate item",
  grand_total: "Grand-total mismatch",
  qty_outlier: "Quantity outlier",
  // scope-gap categories
  dewatering: "Dewatering",
  shoring: "Shoring / earth retention",
  anti_termite: "Anti-termite treatment",
  backfilling: "Backfilling",
  soil_disposal: "Surplus-earth disposal",
  waterproofing: "Waterproofing",
  earthing: "Earthing",
};

export const categoryLabel = (c: string): string => CATEGORY[c] ?? humanize(c);

const STATUS: Record<string, string> = {
  // opportunity status
  reviewing: "Reviewing",
  reviewed: "Reviewed",
  bid: "Bid submitted",
  won: "Won",
  lost: "Lost",
  declined: "Declined",
  // review status
  proposed: "To review",
  accepted: "Accepted",
  edited: "Edited",
  rejected: "Rejected",
};

export const statusLabel = (s: string): string => STATUS[s] ?? humanize(s);

const DEADLINE: Record<string, string> = {
  submission: "Bid submission",
  prebid_meeting: "Pre-bid meeting",
  clarification: "Clarification cut-off",
  validity: "Bid validity",
  emd: "EMD",
  completion_milestone: "Completion",
};

export const deadlineLabel = (k: string): string => DEADLINE[k] ?? humanize(k);

const ARTIFACT: Record<string, string> = {
  clarification_letter: "Clarification letter",
  assumptions_register: "Assumptions & exclusions register",
};

export const artifactLabel = (k: string): string => ARTIFACT[k] ?? humanize(k);

const DOC_KIND: Record<string, string> = {
  nit: "Notice Inviting Tender",
  gcc: "General Conditions",
  scc: "Special Conditions",
  boq: "Bill of Quantities",
  spec: "Specifications",
  addendum: "Addendum",
  drawing: "Drawing",
};

export const docKindLabel = (k: string): string => DOC_KIND[k] ?? humanize(k);
