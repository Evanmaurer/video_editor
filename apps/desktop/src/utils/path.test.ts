import { describe, expect, it } from "vitest";
import { joinPath } from "./path";

describe("joinPath", () => {
  it("joins base and segment", () => {
    expect(joinPath("/Users/test/Montages", "MyProject")).toBe("/Users/test/Montages/MyProject");
  });

  it("strips trailing slashes from base", () => {
    expect(joinPath("/Users/test/Montages/", "MyProject")).toBe("/Users/test/Montages/MyProject");
  });
});
