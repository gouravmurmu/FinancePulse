import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerText } from "./answer-text";

describe("AnswerText", () => {
  it("renders labels, bold and bullets without raw HTML", () => {
    const { container } = render(
      <AnswerText
        text={
          "[Fact] Apple closed at **$200**.\n\n- [Computed] Volatility 25%\n- <img src=x onerror=alert(1)>"
        }
      />,
    );
    expect(screen.getByText("Fact")).toBeInTheDocument();
    expect(screen.getByText("Computed")).toBeInTheDocument();
    expect(screen.getByText("$200").tagName).toBe("STRONG");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("img")).toBeNull();
  });
});
