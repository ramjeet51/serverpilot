"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { env } from "@/lib/env";
import { loginSchema } from "@/lib/validation";

type FormValues = { email: string; password: string };

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const form = useForm<FormValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  async function onSubmit(values: FormValues) {
    try {
      await login(values.email, values.password);
      router.replace("/dashboard");
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Could not sign in";
      toast.error(message);
      form.setError("root", { message });
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="grid-fade relative hidden flex-col justify-between p-10 lg:flex">
        <p className="font-display text-3xl">{env.appName}</p>
        <div>
          <h1 className="max-w-md font-display text-5xl leading-tight">Manage Ubuntu servers from one control plane.</h1>
          <p className="mt-4 max-w-md text-muted-foreground">
            This Mac runs the management server. Agents on your Ubuntu machines connect outbound. No public database, no dummy controls.
          </p>
        </div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Phase 1 · Authentication and jobs</p>
      </section>
      <section className="flex items-center justify-center px-4 py-12">
        <form onSubmit={form.handleSubmit(onSubmit)} className="panel w-full max-w-md space-y-5 p-6 sm:p-8" noValidate>
          <div className="lg:hidden">
            <p className="font-display text-2xl">{env.appName}</p>
          </div>
          <div>
            <h2 className="font-display text-3xl">Sign in</h2>
            <p className="mt-1 text-sm text-muted-foreground">Use the administrator account created during setup.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="username" {...form.register("email")} />
            {form.formState.errors.email && <p className="text-sm text-danger">{form.formState.errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="current-password" {...form.register("password")} />
            {form.formState.errors.password && <p className="text-sm text-danger">{form.formState.errors.password.message}</p>}
          </div>
          {form.formState.errors.root && <p className="text-sm text-danger">{form.formState.errors.root.message}</p>}
          <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </section>
    </div>
  );
}
