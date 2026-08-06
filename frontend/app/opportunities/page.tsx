"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Opportunity } from "@/lib/api";
import { useSession } from "@/components/session";
import { CountdownBadge } from "@/components/badges";
import { statusLabel } from "@/lib/labels";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function OpportunitiesPage() {
  const { session } = useSession();
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!session) return;
    const { opportunities } = await api.listOpportunities(session.token);
    setOpps(opportunities);
    setLoading(false);
  }

  useEffect(() => {
    if (session) refresh();
    else setLoading(false);
  }, [session]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !title.trim()) return;
    await api.createOpportunity(session.token, title.trim());
    setTitle("");
    refresh();
  }

  if (!session) {
    return (
      <div className="space-y-6">
        <EmptyState
          title="Sign in to see your opportunities"
          body="Your opportunity board is your countdown wall — every live tender, days to submission, and review status at a glance."
          cta={{ href: "/login", label: "Sign in to continue" }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-text-primary">Opportunities</h1>
        <p className="text-text-secondary">
          Track all your active tenders. Red indicates &lt; 3 days to submission, amber &lt; 7 days.
        </p>
      </div>

      {/* Create Opportunity Form */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={create} className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <Input
                placeholder="New tender title…"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                help="Enter the tender name or reference number"
              />
            </div>
            <Button
              type="submit"
              variant="primary"
              size="md"
              className="sm:mt-6"
            >
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Opportunities Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-center text-text-muted">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-border-default border-t-ink mb-3" />
            <p className="text-sm">Loading opportunities…</p>
          </div>
        </div>
      ) : opps.length === 0 ? (
        <EmptyState
          title="No opportunities yet"
          body="Create your first tender above, then upload the GCC as well — 60% of traps live in the conditions, not just the NIT."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {opps.map((o) => (
            <Link
              key={o.id}
              href={`/opportunities/${o.id}`}
            >
              <Card className="h-full hover:shadow-md hover:border-ink transition-all duration-base cursor-pointer">
                <CardContent className="pt-6 space-y-4">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-text-primary truncate text-base">
                        {o.title}
                      </h3>
                    </div>
                    <Badge variant="secondary" size="sm" className="flex-shrink-0">
                      {statusLabel(o.status)}
                    </Badge>
                  </div>

                  {/* Deadline */}
                  <div>
                    <div className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
                      Submission Deadline
                    </div>
                    <CountdownBadge due={o.submission_due} />
                  </div>

                  {/* CTA */}
                  <div className="pt-2 text-sm text-ink font-medium hover:underline">
                    Open workbench →
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState({
  title,
  body,
  cta,
}: {
  title: string;
  body: string;
  cta?: { href: string; label: string };
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="py-12 text-center space-y-4">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold text-text-primary">{title}</h2>
          <p className="text-text-secondary max-w-md mx-auto">{body}</p>
        </div>
        {cta && (
          <div className="pt-2">
            <Link href={cta.href}>
              <Button variant="primary" size="md">
                {cta.label}
              </Button>
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
