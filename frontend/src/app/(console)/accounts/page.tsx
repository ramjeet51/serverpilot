"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/types";
import { formatWhen } from "@/lib/utils";
import { accountSchema } from "@/lib/validation";

type FormValues = { email: string; full_name: string; password: string; roles: Array<"admin" | "operator" | "viewer"> };

export default function AccountsPage() {
  const { can, user: current } = useAuth();
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<User[]>("/api/v1/accounts") });
  const form = useForm<FormValues>({
    resolver: zodResolver(accountSchema),
    defaultValues: { email: "", full_name: "", password: "", roles: ["viewer"] },
  });

  const create = useMutation({
    mutationFn: (values: FormValues) => api<User>("/api/v1/accounts", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => {
      toast.success("Account created");
      setOpen(false);
      form.reset();
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not create the account"),
  });

  const toggle = useMutation({
    mutationFn: (account: User) => api<User>(`/api/v1/accounts/${account.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !account.is_active }),
    }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["accounts"] }),
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Update failed"),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl">Accounts</h1>
          <p className="mt-1 text-sm text-muted-foreground">Platform users. These are not Linux accounts on managed servers.</p>
        </div>
        {can("accounts:write") && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>New account</Button></DialogTrigger>
            <DialogContent title="Create account">
              <form className="space-y-3" onSubmit={form.handleSubmit((values) => create.mutate(values))}>
                <Field label="Email" error={form.formState.errors.email?.message}>
                  <Input type="email" {...form.register("email")} />
                </Field>
                <Field label="Name" error={form.formState.errors.full_name?.message}>
                  <Input {...form.register("full_name")} />
                </Field>
                <Field label="Password" error={form.formState.errors.password?.message}>
                  <Input type="password" {...form.register("password")} />
                </Field>
                <Field label="Role" error={form.formState.errors.roles?.message}>
                  <select className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm" {...form.register("roles.0")}>
                    <option value="viewer">Viewer</option>
                    <option value="operator">Operator</option>
                    <option value="admin">Admin</option>
                  </select>
                </Field>
                <Button type="submit" disabled={create.isPending}>Create</Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <tbody>
            {(accounts.data ?? []).map((account) => (
              <tr key={account.id} className="border-t border-border">
                <td className="px-5 py-3">
                  <p>{account.email}</p>
                  <p className="text-xs text-muted-foreground">{account.full_name || "No name"} · {formatWhen(account.created_at)}</p>
                </td>
                <td className="px-3 py-3">{account.roles.join(", ")}</td>
                <td className="px-3 py-3"><Badge value={account.is_active ? "ok" : "offline"} label={account.is_active ? "active" : "inactive"} /></td>
                <td className="px-5 py-3 text-right">
                  {can("accounts:write") && account.id !== current?.id && (
                    <Button size="sm" variant="outline" onClick={() => toggle.mutate(account)}>
                      {account.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {accounts.isError && <p className="p-5 text-sm text-danger">You need the accounts:read permission.</p>}
      </div>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}
