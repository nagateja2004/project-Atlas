import type { ButtonHTMLAttributes, InputHTMLAttributes, PropsWithChildren, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "../lib/utils";

export function Card({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <section className={cn("rounded-xl border border-slate-200 bg-white p-5 shadow-sm", className)}>{children}</section>;
}

export function Button({ className, variant = "primary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-navy text-white hover:bg-[#132f52]",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-rose-700 text-white hover:bg-rose-800",
  };
  return <button className={cn("inline-flex h-9 items-center justify-center rounded-md px-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50", styles[variant], className)} {...props} />;
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none ring-signal focus:ring-2", className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("min-h-20 w-full rounded-md border border-slate-300 bg-white p-3 text-sm outline-none ring-signal focus:ring-2", className)} {...props} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn("h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none ring-signal focus:ring-2", className)} {...props} />;
}

export function Badge({ children, tone = "slate" }: PropsWithChildren<{ tone?: "slate" | "green" | "amber" | "red" | "blue" }>) {
  const styles = { slate: "bg-slate-100 text-slate-700", green: "bg-emerald-100 text-emerald-800", amber: "bg-amber-100 text-amber-900", red: "bg-rose-100 text-rose-800", blue: "bg-sky-100 text-sky-800" };
  return <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-semibold", styles[tone])}>{children}</span>;
}
