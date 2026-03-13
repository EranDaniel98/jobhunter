import { describe, it, expect } from "vitest";
import {
  loginSchema,
  registerSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
  changePasswordSchema,
} from "../schemas/auth";

// ---------------------------------------------------------------------------
// loginSchema
// ---------------------------------------------------------------------------

describe("loginSchema", () => {
  it("accepts valid email and password", () => {
    const result = loginSchema.safeParse({
      email: "user@example.com",
      password: "secret",
    });
    expect(result.success).toBe(true);
  });

  it("rejects invalid email", () => {
    const result = loginSchema.safeParse({
      email: "not-an-email",
      password: "secret",
    });
    expect(result.success).toBe(false);
  });

  it("rejects empty password", () => {
    const result = loginSchema.safeParse({
      email: "user@example.com",
      password: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects missing fields", () => {
    const result = loginSchema.safeParse({});
    expect(result.success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// registerSchema
// ---------------------------------------------------------------------------

describe("registerSchema", () => {
  const valid = {
    fullName: "Jane Doe",
    email: "jane@example.com",
    password: "StrongPass1",
    confirmPassword: "StrongPass1",
    emailNotifications: true,
  };

  it("accepts a valid registration", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true);
  });

  it("rejects name shorter than 2 chars", () => {
    const result = registerSchema.safeParse({ ...valid, fullName: "J" });
    expect(result.success).toBe(false);
  });

  it("rejects name with invalid characters", () => {
    const result = registerSchema.safeParse({ ...valid, fullName: "Jane<>" });
    expect(result.success).toBe(false);
  });

  it("rejects password without uppercase", () => {
    const result = registerSchema.safeParse({
      ...valid,
      password: "nouppercase1",
      confirmPassword: "nouppercase1",
    });
    expect(result.success).toBe(false);
  });

  it("rejects password without lowercase", () => {
    const result = registerSchema.safeParse({
      ...valid,
      password: "NOLOWERCASE1",
      confirmPassword: "NOLOWERCASE1",
    });
    expect(result.success).toBe(false);
  });

  it("rejects password without digit", () => {
    const result = registerSchema.safeParse({
      ...valid,
      password: "NoDigitHere",
      confirmPassword: "NoDigitHere",
    });
    expect(result.success).toBe(false);
  });

  it("rejects password shorter than 8 chars", () => {
    const result = registerSchema.safeParse({
      ...valid,
      password: "Ab1",
      confirmPassword: "Ab1",
    });
    expect(result.success).toBe(false);
  });

  it("rejects mismatched passwords", () => {
    const result = registerSchema.safeParse({
      ...valid,
      confirmPassword: "Different1",
    });
    expect(result.success).toBe(false);
  });

  it("rejects invalid email", () => {
    const result = registerSchema.safeParse({ ...valid, email: "bad" });
    expect(result.success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// forgotPasswordSchema
// ---------------------------------------------------------------------------

describe("forgotPasswordSchema", () => {
  it("accepts valid email", () => {
    const result = forgotPasswordSchema.safeParse({
      email: "user@example.com",
    });
    expect(result.success).toBe(true);
  });

  it("rejects invalid email", () => {
    const result = forgotPasswordSchema.safeParse({ email: "nope" });
    expect(result.success).toBe(false);
  });

  it("rejects empty email", () => {
    const result = forgotPasswordSchema.safeParse({ email: "" });
    expect(result.success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// resetPasswordSchema
// ---------------------------------------------------------------------------

describe("resetPasswordSchema", () => {
  const valid = { password: "NewPass1x", confirmPassword: "NewPass1x" };

  it("accepts valid matching passwords", () => {
    expect(resetPasswordSchema.safeParse(valid).success).toBe(true);
  });

  it("rejects password without uppercase", () => {
    const result = resetPasswordSchema.safeParse({
      password: "newpass1x",
      confirmPassword: "newpass1x",
    });
    expect(result.success).toBe(false);
  });

  it("rejects password without number", () => {
    const result = resetPasswordSchema.safeParse({
      password: "NewPassxx",
      confirmPassword: "NewPassxx",
    });
    expect(result.success).toBe(false);
  });

  it("rejects mismatched passwords", () => {
    const result = resetPasswordSchema.safeParse({
      password: "NewPass1x",
      confirmPassword: "Different1",
    });
    expect(result.success).toBe(false);
  });

  it("rejects short password", () => {
    const result = resetPasswordSchema.safeParse({
      password: "Ab1",
      confirmPassword: "Ab1",
    });
    expect(result.success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// changePasswordSchema
// ---------------------------------------------------------------------------

describe("changePasswordSchema", () => {
  const valid = {
    currentPassword: "oldpass",
    newPassword: "NewPass1x",
    confirmPassword: "NewPass1x",
  };

  it("accepts valid change request", () => {
    expect(changePasswordSchema.safeParse(valid).success).toBe(true);
  });

  it("rejects empty current password", () => {
    const result = changePasswordSchema.safeParse({
      ...valid,
      currentPassword: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects weak new password", () => {
    const result = changePasswordSchema.safeParse({
      ...valid,
      newPassword: "weak",
      confirmPassword: "weak",
    });
    expect(result.success).toBe(false);
  });

  it("rejects mismatched confirm password", () => {
    const result = changePasswordSchema.safeParse({
      ...valid,
      confirmPassword: "Mismatch1",
    });
    expect(result.success).toBe(false);
  });
});
