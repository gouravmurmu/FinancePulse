import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useIsPro } from "@/lib/view-mode";
import { ViewToggle } from "./view-toggle";

function ProOnly() {
  return useIsPro() ? <p>Pro detail</p> : null;
}

describe("ViewToggle", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to Simple and remembers Pro", () => {
    render(
      <>
        <ViewToggle />
        <ProOnly />
      </>,
    );
    expect(screen.getByRole("radio", { name: "Simple" })).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByText("Pro detail")).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Pro" }));
    expect(screen.getByText("Pro detail")).toBeInTheDocument();
    expect(localStorage.getItem("marketpulse.view")).toBe("pro");
  });
});
