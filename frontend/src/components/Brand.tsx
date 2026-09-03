import clsx from "clsx";
import acewinLogoDark from "../assets/acewin-logo-dark-bg.png";
import acewinLogoLight from "../assets/acewin-logo-light-bg.png";
import acewinMarkDark from "../assets/acewin-mark-dark-bg.png";
import acewinWordmarkDark from "../assets/acewin-wordmark-dark-bg.png";

/**
 * The ACEWIN logo, cropped directly from the real artwork (not a redrawn
 * approximation) with a transparent background, so it drops cleanly onto
 * any surface with no box around it.
 *
 *  - `acewin-logo-dark-bg.png`: the full vertical lockup (mark stacked over
 *    the "ACEWIN" wordmark) as originally designed — teal mark, off-white
 *    wordmark, for dark surfaces. Used where there's vertical room to show
 *    it at full size (e.g. the Login/Register hero panels).
 *  - `acewin-mark-dark-bg.png` / `acewin-wordmark-dark-bg.png`: the same
 *    artwork split into its two pieces and laid out side by side, for tight
 *    horizontal spots (sticky top bars, the sidebar header row) — the
 *    lockup is naturally tall and narrow, so showing it full-size there
 *    would grow those bars; laid out horizontally it fits the same footprint
 *    the old icon+text row used, without changing their height.
 *  - `acewin-logo-light-bg.png`: teal mark + dark-navy wordmark, for
 *    white/light surfaces (kept here for future light-background spots —
 *    printed/exported documents, etc. — nothing in-app is light-themed
 *    today, so it isn't wired into `AcewinLogo` below).
 */
export { acewinLogoDark, acewinLogoLight };

// Row height (px) each tier occupied under the old icon+text lockup —
// preserved exactly so swapping in the real artwork doesn't change the
// height of whatever bar/panel the logo sits in.
const ROW_HEIGHT: Record<"lg" | "xl" | "2xl", number> = {
  lg: 28,
  xl: 28,
  "2xl": 32,
};

// Natural pixel dimensions of the source crops, used to scale the icon and
// wordmark pieces together (by the icon's height) so their relative size
// matches the original artwork.
const MARK_NATURAL = { w: 560, h: 401 };
const WORDMARK_NATURAL = { w: 882, h: 190 };

export function AcewinLogo({
  wordmarkSize = "xl",
  className,
}: {
  markSize?: number;
  wordmarkSize?: "lg" | "xl" | "2xl";
  variant?: "white" | "ink";
  className?: string;
}) {
  const rowHeight = ROW_HEIGHT[wordmarkSize];

  // The Login/Register hero panels have vertical room to spare, so show the
  // full vertical lockup exactly as designed, scaled up a bit past the old
  // row height for a proper hero size.
  if (wordmarkSize === "2xl") {
    const heroHeight = rowHeight * 2.25;
    return (
      <img
        src={acewinLogoDark}
        alt="ACEWIN"
        style={{ height: heroHeight, width: "auto" }}
        className={clsx("shrink-0", className)}
      />
    );
  }

  // Tight sticky bars: lay the mark and wordmark out horizontally, scaled
  // together by the icon's natural height, so the row keeps its original height.
  const scale = rowHeight / MARK_NATURAL.h;
  const markWidth = MARK_NATURAL.w * scale;
  const wordmarkHeight = WORDMARK_NATURAL.h * scale;
  const wordmarkWidth = WORDMARK_NATURAL.w * scale;

  return (
    <span className={clsx("flex items-center gap-2", className)} style={{ height: rowHeight }}>
      <img
        src={acewinMarkDark}
        alt=""
        style={{ height: rowHeight, width: markWidth }}
        className="shrink-0"
      />
      <img
        src={acewinWordmarkDark}
        alt="ACEWIN"
        style={{ height: wordmarkHeight, width: wordmarkWidth }}
        className="shrink-0"
      />
    </span>
  );
}
