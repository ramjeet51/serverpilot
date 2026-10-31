import { z } from "zod";

export const loginSchema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Password is required").max(256),
});

export const passwordSchema = z
  .string()
  .min(12, "Use at least 12 characters")
  .max(256)
  .refine((value) => {
    const checks = [/[a-z]/.test(value), /[A-Z]/.test(value), /\d/.test(value), /[^a-zA-Z0-9]/.test(value)];
    return checks.filter(Boolean).length >= 3;
  }, "Use at least three of: lowercase, uppercase, digit, symbol");

export const accountSchema = z.object({
  email: z.email("Enter a valid email"),
  full_name: z.string().max(255),
  password: passwordSchema,
  roles: z.array(z.enum(["admin", "operator", "viewer"])).min(1, "Choose a role"),
});

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: passwordSchema,
    confirm: z.string(),
  })
  .refine((value) => value.new_password === value.confirm, { path: ["confirm"], message: "Passwords do not match" });
