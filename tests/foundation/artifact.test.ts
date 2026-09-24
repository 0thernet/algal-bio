import { expect, test } from "bun:test";

test("Bun and Python share the portable UTF-8 artifact identity", async () => {
  const fixture = await Bun.file(new URL("./fixtures/artifact.json", import.meta.url)).json();
  const bytes = new TextEncoder().encode(fixture.source);
  const digest = new Bun.CryptoHasher("sha256").update(bytes).digest("hex");
  expect({ sha256: digest, bytes: bytes.byteLength }).toEqual(fixture.expected);
  expect(fixture.license).toBe("MIT");
});
