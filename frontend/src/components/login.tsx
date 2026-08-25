"use client";

import { FormEvent, useState } from "react";

import { ApiError, api } from "../lib/api";
import { Button, Card, Input, Notice } from "./ui";

export function Login({
  onSignedIn,
  reason,
  onBack,
}: {
  onSignedIn: () => void;
  reason?: string | null;
  onBack?: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.login(email.trim(), password);
      // Hold the success state briefly so the transition reads as an outcome
      // rather than the form vanishing mid-click.
      setDone(true);
      onSignedIn();
    } catch (caught) {
      // The API answers every failure - unknown address, wrong password,
      // deactivated account - with one message on purpose, so that a wrong
      // guess cannot be used to discover which addresses exist. Repeating it
      // verbatim keeps that property instead of guessing at a friendlier
      // reason the API declined to give.
      setError(
        caught instanceof ApiError && caught.status === 401
          ? "Invalid email or password."
          : caught instanceof ApiError
            ? caught.message
            : "Unable to reach Project Atlas. Check the API service and try again.",
      );
      setPassword("");
      setSubmitting(false);
    }
  };

  return (
    <main className="relative isolate flex min-h-screen items-center justify-center overflow-hidden bg-navy-bloom px-6 py-12">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[.14]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,.5) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(70% 60% at 50% 25%, black 20%, transparent 100%)",
          WebkitMaskImage: "radial-gradient(70% 60% at 50% 25%, black 20%, transparent 100%)",
        }}
      />

      <div className="relative w-full max-w-sm animate-rise">
        <div className="mb-7 text-center">
          <p className="font-mono text-label uppercase tracking-wider text-sky-300/80">
            EPC project intelligence
          </p>
          <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-white">Project Atlas</h1>
        </div>

        <Card className="shadow-lift">
          {reason ? <Notice kind="info">{reason}</Notice> : null}

          <form onSubmit={submit} className="space-y-3.5">
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block font-mono text-label uppercase tracking-wider text-muted"
              >
                Email
              </label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                autoFocus
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block font-mono text-label uppercase tracking-wider text-muted"
              >
                Password
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>

            {error ? <Notice kind="error">{error}</Notice> : null}
            {done && !error ? <Notice kind="success">Signed in. Opening the workspace…</Notice> : null}

            <Button
              type="submit"
              size="lg"
              variant="signal"
              className="w-full"
              loading={submitting}
              disabled={!email || !password}
            >
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>

        <div className="mt-5 space-y-3 text-center">
          <p className="text-xs leading-5 text-sky-100/60">
            Accounts are created by an administrator. There is no self-service sign-up and no
            password reset flow.
          </p>
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="text-xs font-semibold text-sky-200/90 underline decoration-sky-200/40 underline-offset-4 transition-crisp hover:text-white hover:decoration-white/70"
            >
              ← Back to the overview
            </button>
          ) : null}
        </div>
      </div>
    </main>
  );
}
