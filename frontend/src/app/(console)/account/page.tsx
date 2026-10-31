"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { changePasswordSchema } from "@/lib/validation";

type FormValues = { current_password: string; new_password: string; confirm: string };

export default function AccountPage() {
  const { user } = useAuth();
  const form = useForm<FormValues>({ resolver: zodResolver(changePasswordSchema), defaultValues: { current_password: "", new_password: "", confirm: "" } });

  async function onSubmit(values: FormValues) {
    try {
      await api("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: values.current_password, new_password: values.new_password }),
      });
      toast.success("Password updated");
      form.reset();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not change the password");
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="font-display text-3xl sm:text-4xl">Security</h1>
        <p className="mt-1 text-sm text-muted-foreground">{user?.email}</p>
      </div>
      <form className="panel space-y-4 p-5" onSubmit={form.handleSubmit(onSubmit)}>
        <h2 className="font-display text-xl">Change password</h2>
        <div className="space-y-1">
          <Label htmlFor="current">Current password</Label>
          <Input id="current" type="password" autoComplete="current-password" {...form.register("current_password")} />
          {form.formState.errors.current_password && <p className="text-sm text-danger">{form.formState.errors.current_password.message}</p>}
        </div>
        <div className="space-y-1">
          <Label htmlFor="next">New password</Label>
          <Input id="next" type="password" autoComplete="new-password" {...form.register("new_password")} />
          {form.formState.errors.new_password && <p className="text-sm text-danger">{form.formState.errors.new_password.message}</p>}
        </div>
        <div className="space-y-1">
          <Label htmlFor="confirm">Confirm new password</Label>
          <Input id="confirm" type="password" autoComplete="new-password" {...form.register("confirm")} />
          {form.formState.errors.confirm && <p className="text-sm text-danger">{form.formState.errors.confirm.message}</p>}
        </div>
        <Button type="submit" disabled={form.formState.isSubmitting}>Update password</Button>
      </form>
    </div>
  );
}
