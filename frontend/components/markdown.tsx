"use client";

import { useMemo, type JSX } from "react";

type InlineNode = { kind: "text" | "bold" | "italic" | "code" | "link"; text: string; href?: string };

const URL_SCHEME_RE = /^([a-z][a-z0-9+.-]*):/i;

function isAllowedHref(href: string): boolean {
  const trimmed = href.trim();
  if (!trimmed) return false;
  // Allow relative paths, anchors, and query-only URLs.
  if (trimmed.startsWith("/") || trimmed.startsWith("#") || trimmed.startsWith("?")) {
    return true;
  }
  const match = trimmed.match(URL_SCHEME_RE);
  if (!match) return true; // no scheme, e.g. example.com/path
  const scheme = match[1].toLowerCase();
  return ["http", "https", "mailto", "tel", "sms", "callto"].includes(scheme);
}

function parseInline(text: string): InlineNode[] {
  const nodes: InlineNode[] = [];
  let i = 0;
  while (i < text.length) {
    const rest = text.slice(i);
    const bold = rest.match(/^(\*\*|__)(.+?)\1/);
    const italic = rest.match(/^(\*|_)(.+?)\1/);
    const code = rest.match(/^`([^`]+)`/);
    const link = rest.match(/^\[([^\]]+)\]\(([^)]+)\)/);
    if (bold) {
      nodes.push({ kind: "bold", text: bold[2] });
      i += bold[0].length;
    } else if (italic) {
      nodes.push({ kind: "italic", text: italic[2] });
      i += italic[0].length;
    } else if (code) {
      nodes.push({ kind: "code", text: code[1] });
      i += code[0].length;
    } else if (link) {
      nodes.push({ kind: "link", text: link[1], href: link[2] });
      i += link[0].length;
    } else {
      // collect plain text until next special token
      const next = rest.search(/\*\*|\*|_|`|\[/) || 0;
      const len = next > 0 ? next : rest.length;
      nodes.push({ kind: "text", text: rest.slice(0, len) });
      i += len;
    }
  }
  return nodes;
}

function Inline({ nodes }: { nodes: InlineNode[] }) {
  return (
    <>
      {nodes.map((n, idx) => {
        if (n.kind === "bold") return <strong key={idx}>{n.text}</strong>;
        if (n.kind === "italic") return <em key={idx}>{n.text}</em>;
        if (n.kind === "code") return <code key={idx} className="rounded bg-slate-100 px-1 py-0.5 text-xs font-mono text-slate-700">{n.text}</code>;
        if (n.kind === "link") {
          if (!n.href || !isAllowedHref(n.href)) {
            return <span key={idx} className="text-slate-700" title={n.href}>{n.text}</span>;
          }
          return <a key={idx} href={n.href} className="text-blue-600 underline" target="_blank" rel="noopener noreferrer">{n.text}</a>;
        }
        return <span key={idx}>{n.text}</span>;
      })}
    </>
  );
}

type Block =
  | { kind: "paragraph"; children: InlineNode[] }
  | { kind: "heading"; level: number; children: InlineNode[] }
  | { kind: "code"; language?: string; content: string }
  | { kind: "ul"; items: InlineNode[][] }
  | { kind: "ol"; items: InlineNode[][] }
  | { kind: "quote"; children: InlineNode[] }
  | { kind: "hr" };

function parseBlocks(src: string): Block[] {
  const lines = src.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  function flushParagraph(buf: string[]) {
    if (buf.length) {
      blocks.push({ kind: "paragraph", children: parseInline(buf.join(" ")) });
    }
  }

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed === "") {
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const fence = trimmed.slice(0, 3);
      const lang = trimmed.slice(3).trim() || undefined;
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // skip closing fence
      blocks.push({ kind: "code", language: lang, content: code.join("\n") });
      continue;
    }

    if (/^#{1,6}\s/.test(trimmed)) {
      const match = trimmed.match(/^(#{1,6})\s+(.*)$/);
      if (match) {
        blocks.push({ kind: "heading", level: match[1].length, children: parseInline(match[2]) });
        i += 1;
        continue;
      }
    }

    if (/^[-*]\s/.test(trimmed)) {
      const items: InlineNode[][] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i].trim())) {
        items.push(parseInline(lines[i].trim().replace(/^[-*]\s/, "")));
        i += 1;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      const items: InlineNode[][] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        items.push(parseInline(lines[i].trim().replace(/^\d+\.\s/, "")));
        i += 1;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }

    if (trimmed.startsWith("> ")) {
      const quote: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("> ")) {
        quote.push(lines[i].trim().slice(2));
        i += 1;
      }
      blocks.push({ kind: "quote", children: parseInline(quote.join(" ")) });
      continue;
    }

    if (/^---\s*$/.test(trimmed) || /^___\s*$/.test(trimmed) || /^\*\*\*\s*$/.test(trimmed)) {
      blocks.push({ kind: "hr" });
      i += 1;
      continue;
    }

    const paragraph: string[] = [];
    while (i < lines.length && lines[i].trim() !== "" && !/^#{1,6}\s|^[-*]\s|^\d+\.\s|^> |^```|^---\s*$/.test(lines[i].trim())) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    flushParagraph(paragraph);
  }

  return blocks;
}

export function Markdown({ source }: { source: string }) {
  const blocks = useMemo(() => parseBlocks(source), [source]);
  return (
    <div className="prose prose-sm max-w-none prose-slate">
      {blocks.map((b, idx) => {
        if (b.kind === "heading") {
          const Tag = `h${b.level}` as keyof JSX.IntrinsicElements;
          return (
            <Tag key={idx} className="font-semibold text-ink">
              <Inline nodes={b.children} />
            </Tag>
          );
        }
        if (b.kind === "paragraph") {
          return (
            <p key={idx} className="whitespace-pre-wrap leading-relaxed">
              <Inline nodes={b.children} />
            </p>
          );
        }
        if (b.kind === "code") {
          return (
            <pre key={idx} className="rounded-md bg-slate-50 p-3 text-xs font-mono text-slate-700">
              <code>{b.content}</code>
            </pre>
          );
        }
        if (b.kind === "ul") {
          return (
            <ul key={idx} className="list-disc space-y-1 pl-5">
              {b.items.map((item, i2) => (
                <li key={i2}>
                  <Inline nodes={item} />
                </li>
              ))}
            </ul>
          );
        }
        if (b.kind === "ol") {
          return (
            <ol key={idx} className="list-decimal space-y-1 pl-5">
              {b.items.map((item, i2) => (
                <li key={i2}>
                  <Inline nodes={item} />
                </li>
              ))}
            </ol>
          );
        }
        if (b.kind === "quote") {
          return (
            <blockquote key={idx} className="border-l-4 border-slate-300 pl-4 italic text-slate-600">
              <Inline nodes={b.children} />
            </blockquote>
          );
        }
        if (b.kind === "hr") {
          return <hr key={idx} className="my-4 border-slate-200" />;
        }
        return null;
      })}
    </div>
  );
}
