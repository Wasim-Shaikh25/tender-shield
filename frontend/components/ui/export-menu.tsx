"use client";

import { useState } from "react";
import { API_BASE } from "@/lib/api";
import { Button } from "./button";
import { Dropdown, DropdownItem } from "./dropdown";
import { EmailDialog } from "./email-dialog";

interface ExportMenuProps {
  opportunityId: string;
  opportunityTitle: string;
  token: string;
  disabled?: boolean;
  onEmailOpen?: (open: boolean) => void;
}

export function ExportMenu({
  opportunityId,
  opportunityTitle,
  token,
  disabled = false,
  onEmailOpen,
}: ExportMenuProps) {
  const [emailOpen, setEmailOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleEmailOpen = (open: boolean) => {
    setEmailOpen(open);
    onEmailOpen?.(open);
  };

  const handlePdfExport = async () => {
    setBusy(true);
    try {
      const res = await fetch(
        `${API_BASE}/export/opportunities/${opportunityId}?format=pdf`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `bid-review-${opportunityId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  };

  const handleDocxExport = async () => {
    setBusy(true);
    try {
      const res = await fetch(
        `${API_BASE}/export/opportunities/${opportunityId}?format=docx`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `bid-review-${opportunityId}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  };

  const handleXlsxExport = async () => {
    setBusy(true);
    try {
      const res = await fetch(
        `${API_BASE}/export/opportunities/${opportunityId}?format=xlsx`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `bid-review-${opportunityId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Dropdown
        trigger={
          <Button variant="secondary" size="md" disabled={disabled || busy}>
            {busy ? "Exporting…" : "Export"}
          </Button>
        }
      >
        <DropdownItem onClick={handlePdfExport} disabled={busy}>
          📄 PDF Export
        </DropdownItem>
        <DropdownItem onClick={handleDocxExport} disabled={busy}>
          📝 Word Document
        </DropdownItem>
        <DropdownItem onClick={handleXlsxExport} disabled={busy}>
          📊 Spreadsheet
        </DropdownItem>
        <div className="border-t border-border-default my-1" />
        <DropdownItem onClick={() => handleEmailOpen(true)}>
          ✉️ Email Summary
        </DropdownItem>
      </Dropdown>

      <EmailDialog
        open={emailOpen}
        onOpenChange={handleEmailOpen}
        opportunityId={opportunityId}
        opportunityTitle={opportunityTitle}
        token={token}
      />
    </>
  );
}
