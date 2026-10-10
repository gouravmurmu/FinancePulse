import { createHmac } from "node:crypto";
import type { BrowserContext, Page } from "@playwright/test";

/** Must match SUPABASE_JWT_SECRET of the API under test. Test-only value. */
const SECRET = process.env.E2E_JWT_SECRET ?? "local-e2e-secret-at-least-32-bytes-long";
export const E2E_USER = "11111111-1111-1111-1111-111111111111";
const SUPABASE = process.env.E2E_SUPABASE_URL ?? "https://fake.supabase.test";

const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString("base64url");

function token(): string {
  const now = Math.floor(Date.now() / 1000);
  const head = b64({ alg: "HS256", typ: "JWT" });
  const body = b64({
    sub: E2E_USER,
    aud: "authenticated",
    role: "authenticated",
    email: "e2e@example.test",
    exp: now + 3600,
  });
  const sig = createHmac("sha256", SECRET).update(`${head}.${body}`).digest("base64url");
  return `${head}.${body}.${sig}`;
}

/** Answers Supabase Auth calls so sign-in works without a real project. */
export async function stubSupabase(ctx: BrowserContext) {
  const user = {
    id: E2E_USER,
    email: "e2e@example.test",
    aud: "authenticated",
    role: "authenticated",
    app_metadata: {},
    user_metadata: {},
    created_at: new Date().toISOString(),
  };
  await ctx.route(`${SUPABASE}/**`, async (route) => {
    const url = route.request().url();
    if (url.includes("/auth/v1/token")) {
      return route.fulfill({
        json: {
          access_token: token(),
          token_type: "bearer",
          expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          refresh_token: "e2e-refresh",
          user,
        },
      });
    }
    if (url.includes("/auth/v1/user")) return route.fulfill({ json: user });
    if (url.includes("/auth/v1/logout")) return route.fulfill({ status: 204, body: "" });
    return route.fulfill({ status: 404, json: {} });
  });
}

export async function signIn(page: Page, next: string) {
  await stubSupabase(page.context());
  await page.goto(`/sign-in?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill("e2e@example.test");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(`**${next}`);
}
