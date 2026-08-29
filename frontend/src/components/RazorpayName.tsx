import { useState, type MouseEvent } from "react";

/** 5×7 glyphs. 1 = a physical LED. */
const GLYPHS: Record<string, number[][]> = {
  R: [
    [1, 1, 1, 1, 0],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 0],
    [1, 0, 1, 0, 0],
    [1, 0, 0, 1, 0],
    [1, 0, 0, 0, 1],
  ],
  A: [
    [0, 1, 1, 1, 0],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
  ],
  Z: [
    [1, 1, 1, 1, 1],
    [0, 0, 0, 0, 1],
    [0, 0, 0, 1, 0],
    [0, 0, 1, 0, 0],
    [0, 1, 0, 0, 0],
    [1, 0, 0, 0, 0],
    [1, 1, 1, 1, 1],
  ],
  O: [
    [0, 1, 1, 1, 0],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [0, 1, 1, 1, 0],
  ],
  P: [
    [1, 1, 1, 1, 0],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 0],
    [1, 0, 0, 0, 0],
    [1, 0, 0, 0, 0],
    [1, 0, 0, 0, 0],
  ],
  Y: [
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [0, 1, 0, 1, 0],
    [0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0],
  ],
};

const WORD = ["R", "A", "Z", "O", "R", "P", "A", "Y"] as const;
const LETTER_MS = 380;
const DOT_MS = 55;

export function RazorpayName({
  className = "",
  size = "sm",
}: {
  className?: string;
  size?: "sm" | "md" | "hero";
}) {
  const [lit, setLit] = useState(false);

  const toggle = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setLit((v) => !v);
  };

  return (
    <button
      type="button"
      className={`rzp-leds rzp-leds-${size} ${lit ? "is-wave-on" : ""} ${className}`}
      aria-label="Razorpay. Click once to light all letters slowly."
      aria-pressed={lit}
      onClick={toggle}
    >
      {WORD.map((ch, i) => (
        <span key={`${ch}-${i}`} className={`rzp-letter ${lit ? "is-on" : ""}`}>
          {GLYPHS[ch].map((row, y) => (
            <span key={y} className="rzp-row">
              {row.map((bit, x) => {
                const delay = i * LETTER_MS + (y * 5 + x) * DOT_MS;
                return (
                  <i
                    key={x}
                    className={`rzp-dot ${bit ? "is-led" : "is-gap"} ${bit && lit ? "is-lit" : ""}`}
                    style={bit ? { animationDelay: `${delay}ms`, transitionDelay: lit ? `${delay}ms` : `${(WORD.length - 1 - i) * 120}ms` } : undefined}
                  />
                );
              })}
            </span>
          ))}
        </span>
      ))}
    </button>
  );
}
