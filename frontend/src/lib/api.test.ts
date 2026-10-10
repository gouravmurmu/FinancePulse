import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ApiError, ApiUnreachableError, apiGet } from "./api";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

describe("apiGet", () => {
  it("parses a successful response with the schema", async () => {
    stubFetch(async () => new Response(JSON.stringify({ a: 1 }), { status: 200 }));
    await expect(apiGet("/x", z.object({ a: z.number() }))).resolves.toEqual({ a: 1 });
  });

  it("treats network failures as an unreachable (waking) server", async () => {
    stubFetch(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(apiGet("/x", z.any())).rejects.toBeInstanceOf(ApiUnreachableError);
  });

  it("treats 503 from the host as an unreachable (waking) server", async () => {
    stubFetch(async () => new Response("", { status: 503 }));
    await expect(apiGet("/x", z.any())).rejects.toBeInstanceOf(ApiUnreachableError);
  });

  it("surfaces the error envelope", async () => {
    stubFetch(
      async () =>
        new Response(JSON.stringify({ error: { code: "not_found", message: "Nope" } }), {
          status: 404,
        }),
    );
    const err = await apiGet("/x", z.any()).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("not_found");
    expect(err.status).toBe(404);
  });
});
