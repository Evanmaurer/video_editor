import { describe, expect, it } from "vitest";
import { formatFetchError } from "@/services/fetch-utils";

describe("formatFetchError", () => {
  it("includes URL and stack trace from Error", () => {
    const original = new Error("Failed to fetch");
    original.stack = "Error: Failed to fetch\n    at fetch (api-client.ts:1:1)";
    const formatted = formatFetchError("http://127.0.0.1:8000/health", original);

    expect(formatted.message).toContain("Failed to fetch");
    expect(formatted.message).toContain("URL: http://127.0.0.1:8000/health");
    expect(formatted.message).toContain("Stack:");
    expect(formatted.message).toContain("api-client.ts");
  });
});
