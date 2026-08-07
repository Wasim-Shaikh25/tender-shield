"use client";

import { useState, useEffect } from "react";
import { API_BASE } from "@/lib/api";
import { Modal } from "./modal";
import { Button } from "./button";
import { Input } from "./input";
import { Alert } from "./alert";

interface EmailData {
  subject: string;
  body: string;
  body_html: string;
  mailto_link: string;
  preview: string;
}

interface EmailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  opportunityId: string;
  opportunityTitle: string;
  token: string;
}

export function EmailDialog({
  open,
  onOpenChange,
  opportunityId,
  opportunityTitle,
  token,
}: EmailDialogProps) {
  const [emailData, setEmailData] = useState<EmailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [recipients, setRecipients] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;

    setLoading(true);
    setError(null);
    setEmailData(null);

    fetch(
      `${API_BASE}/export/opportunities/${opportunityId}/email-summary`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      }
    )
      .then((res) => {
        if (!res.ok) throw new Error("Failed to generate email summary");
        return res.json();
      })
      .then(setEmailData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [open, opportunityId, token]);

  const handleSend = () => {
    if (!emailData) return;
    const { mailto_link } = emailData;
    window.location.href = mailto_link;
    onOpenChange(false);
  };

  const handleCopy = () => {
    if (!emailData) return;
    navigator.clipboard.writeText(emailData.body);
  };

  return (
    <Modal isOpen={open} onClose={() => onOpenChange(false)} title="Email Summary">
      <div className="space-y-4">
        {loading && (
          <p className="text-sm text-text-muted">Generating email summary...</p>
        )}

        {error && (
          <Alert variant="error" title="Error">
            {error}
          </Alert>
        )}

        {emailData && (
          <>
            <div className="space-y-3">
              <div>
                <label htmlFor="email-subject" className="block text-sm font-medium text-text-primary mb-1">
                  Subject
                </label>
                <Input
                  id="email-subject"
                  type="text"
                  value={emailData.subject}
                  readOnly
                  className="bg-background-secondary"
                />
              </div>

              <div>
                <label htmlFor="email-preview" className="block text-sm font-medium text-text-primary mb-1">
                  Message Preview
                </label>
                <div id="email-preview" className="p-3 bg-background-secondary rounded border border-border-default text-sm text-text-secondary max-h-48 overflow-y-auto whitespace-pre-wrap">
                  {emailData.preview}
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="primary"
                  onClick={handleSend}
                  className="flex-1"
                >
                  Open Email Client
                </Button>
                <Button
                  variant="secondary"
                  onClick={handleCopy}
                  className="flex-1"
                >
                  Copy to Clipboard
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
