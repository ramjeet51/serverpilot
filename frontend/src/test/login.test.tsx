import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: null, loading: false, login: vi.fn(), logout: vi.fn(), can: () => false }),
}));

import LoginPage from "@/app/login/page";

describe("login page", () => {
  it("shows validation errors before calling the API", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
  });
});
