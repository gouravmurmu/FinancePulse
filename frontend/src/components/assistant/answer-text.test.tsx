import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerText, parseTable } from "./answer-text";

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

  it("renders a Markdown table, even when squashed onto one line", () => {
    const squashed =
      "| Metric (1yr) | Apple [AAPL] | Microsoft [MSFT] | |---|---|---| | Total return | **+37.8 %** | **+5.6 %** | | Sharpe | 1.44 | 0.33 |";
    expect(parseTable([squashed])).toEqual([
      ["Metric (1yr)", "Apple [AAPL]", "Microsoft [MSFT]"],
      ["Total return", "**+37.8 %**", "**+5.6 %**"],
      ["Sharpe", "1.44", "0.33"],
    ]);
    const { container } = render(
      <AnswerText
        text={"Intro\n\n| A | B |\n|---|---|\n| Beta | 0.67 |\n\nSources: get_risk 【get_risk】"}
      />,
    );
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(screen.getByText("0.67").tagName).toBe("TD");
    expect(container.textContent).not.toContain("【");
  });

  it("leaves text with stray pipes as a paragraph", () => {
    expect(parseTable(["| just a pipe"])).toBeNull();
  });
});
