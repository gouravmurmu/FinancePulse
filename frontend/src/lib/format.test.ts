import { describe, expect, it } from "vitest";
import {
  abbreviate,
  direction,
  formatDate,
  formatMoney,
  formatPercent,
  formatPrice,
} from "./format";

describe("formatMoney", () => {
  it("uses US grouping for USD", () => {
    expect(formatMoney(1234567.5, "USD")).toBe("$1,234,567.50");
  });
  it("uses Indian grouping for INR", () => {
    expect(formatMoney(1234567.5, "INR")).toBe("₹12,34,567.50");
  });
  it("puts a typographic minus before the symbol", () => {
    expect(formatMoney(-42, "USD")).toBe("−$42.00");
  });
});

describe("abbreviate", () => {
  it("uses lakh and crore for INR", () => {
    expect(abbreviate(120000, "INR")).toBe("₹1.2L");
    expect(abbreviate(34000000, "INR")).toBe("₹3.4Cr");
  });
  it("uses K/M/B/T otherwise", () => {
    expect(abbreviate(1200)).toBe("1.2K");
    expect(abbreviate(3400000, "USD")).toBe("$3.4M");
    expect(abbreviate(2.5e12, "USD")).toBe("$2.5T");
  });
  it("keeps small values as-is", () => {
    expect(abbreviate(999)).toBe("999");
  });
});

describe("formatPercent", () => {
  it("signs and rounds to two decimals", () => {
    expect(formatPercent(0.012345)).toBe("+1.23%");
    expect(formatPercent(-0.5)).toBe("−50.00%");
    expect(formatPercent(0)).toBe("0.00%");
  });
});

describe("direction", () => {
  it("pairs a glyph with every move", () => {
    expect(direction(1)).toBe("▲");
    expect(direction(-1)).toBe("▼");
    expect(direction(0)).toBe("•");
  });
});

describe("formatDate", () => {
  it("formats as day month-abbrev year", () => {
    expect(formatDate("2026-10-10T12:00:00Z")).toBe("10 Oct 2026");
  });
  it("respects the time zone", () => {
    // 20:00 UTC on 9 Oct is already 10 Oct in IST.
    expect(formatDate("2026-10-09T20:00:00Z", "Asia/Kolkata")).toBe("10 Oct 2026");
  });
});

describe("formatPrice", () => {
  it("shows index levels without a currency symbol", () => {
    expect(formatPrice(24510.5, "INR", "index")).toBe("24,510.50");
  });
  it("uses the symbol for USD and INR prices", () => {
    expect(formatPrice(182.3, "USD", "equity")).toBe("$182.30");
    expect(formatPrice(123456.7, "INR", "equity")).toBe("₹1,23,456.70");
  });
  it("uses the ISO code for other currencies and 4 decimals below 1", () => {
    expect(formatPrice(0.5123, "EUR", "equity")).toBe("0.5123 EUR");
  });
});
