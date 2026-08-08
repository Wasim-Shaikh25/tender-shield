"use client";

import { useState } from "react";

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatValue(value: unknown, depth = 0): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-slate-400">—</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span
        className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ${
          value ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"
        }`}
      >
        {value ? "Yes" : "No"}
      </span>
    );
  }
  if (typeof value === "number") {
    return <span className="font-mono text-slate-700">{value}</span>;
  }
  if (typeof value === "string") {
    if (value.length > 200) {
      return <TruncatedText text={value} />;
    }
    return <span className="text-slate-700">{value}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-slate-400">0 items</span>;
    return (
      <span className="text-xs text-slate-500">
        {value.length} item{value.length === 1 ? "" : "s"}
      </span>
    );
  }
  if (isPlainObject(value)) {
    if (depth >= 1) {
      return (
        <span className="text-xs text-slate-500">
          {Object.keys(value).length} fields
        </span>
      );
    }
    return <InlineObject data={value} depth={depth + 1} />;
  }
  return <span className="text-slate-700">{String(value)}</span>;
}

function TruncatedText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  if (expanded) {
    return (
      <span className="block whitespace-pre-wrap text-slate-700">
        {text}
        <button
          onClick={() => setExpanded(false)}
          className="ml-2 text-xs text-blue-600 hover:underline"
        >
          Show less
        </button>
      </span>
    );
  }
  return (
    <span className="text-slate-700">
      {text.slice(0, 200)}
      {text.length > 200 && (
        <>
          …
          <button
            onClick={() => setExpanded(true)}
            className="ml-2 text-xs text-blue-600 hover:underline"
          >
            Show more
          </button>
        </>
      )}
    </span>
  );
}

function InlineObject({ data, depth }: { data: Record<string, unknown>; depth: number }) {
  return (
    <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="text-slate-500">{key}</dt>
          <dd className="break-words">{formatValue(value, depth)}</dd>
        </div>
      ))}
    </dl>
  );
}

interface KeyValueSummaryProps {
  data: Record<string, unknown> | unknown[] | null | undefined;
  title?: string;
  maxPreviewKeys?: number;
  rawLabel?: string;
}

export function KeyValueSummary({
  data,
  title,
  maxPreviewKeys = 4,
  rawLabel = "Raw data",
}: KeyValueSummaryProps) {
  if (data === null || data === undefined) return null;

  if (Array.isArray(data)) {
    if (data.length === 0) return <p className="text-sm text-slate-400">0 items</p>;
    return (
      <div className="space-y-2 text-sm">
        {title && <p className="text-xs font-medium uppercase text-slate-500">{title}</p>}
        <ul className="list-inside list-disc text-slate-700">
          {data.slice(0, maxPreviewKeys).map((item, idx) => (
            <li key={idx}>{isPlainObject(item) ? `${Object.keys(item).length} fields` : String(item)}</li>
          ))}
        </ul>
        {data.length > maxPreviewKeys && (
          <details className="text-xs">
            <summary className="cursor-pointer text-slate-500">{rawLabel}</summary>
            <pre className="mt-2 max-h-40 overflow-auto rounded bg-bg-secondary p-2 text-xs text-text-secondary">
              {JSON.stringify(data, null, 2)}
            </pre>
          </details>
        )}
      </div>
    );
  }

  if (!isPlainObject(data)) {
    return <p className="text-sm text-slate-700">{String(data)}</p>;
  }

  const keys = Object.keys(data);
  if (keys.length === 0) return null;

  const previewKeys = keys.slice(0, maxPreviewKeys);
  const extraKeys = keys.slice(maxPreviewKeys);
  const hasNested = Object.values(data).some((v) => isPlainObject(v) || Array.isArray(v));

  return (
    <div className="space-y-2 text-sm">
      {title && <p className="text-xs font-medium uppercase text-slate-500">{title}</p>}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
        {previewKeys.map((key) => (
          <div key={key} className="contents">
            <dt className="text-slate-500">{key}</dt>
            <dd className="break-words text-slate-700">{formatValue(data[key])}</dd>
          </div>
        ))}
      </dl>
      {(extraKeys.length > 0 || hasNested) && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-500">{rawLabel}</summary>
          <pre className="mt-2 max-h-40 overflow-auto rounded bg-bg-secondary p-2 text-xs text-text-secondary">
            {JSON.stringify(data, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
