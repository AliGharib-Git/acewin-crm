import { useEffect, useRef, type ReactNode } from "react";
import clsx from "clsx";

/**
 * Wraps children in a div that fades/slides into place the first time it
 * scrolls into view. Pure CSS transition + IntersectionObserver -- no
 * animation library required. `delay` is in milliseconds and lets a group
 * of siblings stagger in.
 */
export function Reveal({
  children,
  className,
  delay = 0,
  as: Tag = "div",
  variant = "fade",
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "li" | "span";
  /** "fade" (default) slides up; "pop" scales in with a slight overshoot. */
  variant?: "fade" | "pop";
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (typeof IntersectionObserver === "undefined") {
      el.classList.add("in-view");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const Comp = Tag as any;
  return (
    <Comp
      ref={ref}
      className={clsx(variant === "pop" ? "reveal-pop" : "reveal", className)}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Comp>
  );
}
