import { describe, expect, it } from "vitest";

import { accountSchema, loginSchema, passwordSchema } from "@/lib/validation";

describe("login form", () => {
  it("accepts an email and password", () => {
    expect(loginSchema.safeParse({ email: "admin@serverpilot.local", password: "secret" }).success).toBe(true);
  });

  it("rejects a blank password and a malformed email", () => {
    const result = loginSchema.safeParse({ email: "not-an-email", password: "" });
    expect(result.success).toBe(false);
  });
});

describe("password policy", () => {
  it("requires 12 characters and three character classes", () => {
    expect(passwordSchema.safeParse("short").success).toBe(false);
    expect(passwordSchema.safeParse("alllowercase!!").success).toBe(false);
    expect(passwordSchema.safeParse("ServerPilot-1").success).toBe(true);
  });

  it("requires a role when creating an account", () => {
    const result = accountSchema.safeParse({
      email: "ops@serverpilot.local",
      full_name: "Ops",
      password: "ServerPilot-1",
      roles: [],
    });
    expect(result.success).toBe(false);
  });
});
