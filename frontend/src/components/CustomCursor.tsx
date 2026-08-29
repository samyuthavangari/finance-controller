import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

export function CustomCursor() {
  const loc = useLocation();
  const onDash = loc.pathname.startsWith("/app");
  const dot = useRef<HTMLDivElement>(null);
  const ring = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!onDash) return;
    document.documentElement.classList.add("cursor-dash");
    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let rx = x;
    let ry = y;
    let hover = false;
    let raf = 0;

    const move = (e: PointerEvent) => {
      x = e.clientX;
      y = e.clientY;
      const t = e.target as HTMLElement | null;
      hover = Boolean(t?.closest("a, button, [role='button'], summary, .data-table tbody tr"));
    };

    const loop = () => {
      rx += (x - rx) * 0.18;
      ry += (y - ry) * 0.18;
      if (dot.current) {
        dot.current.style.transform = `translate3d(${x}px, ${y}px, 0)`;
        dot.current.classList.toggle("is-hover", hover);
      }
      if (ring.current) {
        ring.current.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
        ring.current.classList.toggle("is-hover", hover);
      }
      raf = requestAnimationFrame(loop);
    };

    window.addEventListener("pointermove", move, { passive: true });
    raf = requestAnimationFrame(loop);
    return () => {
      document.documentElement.classList.remove("cursor-dash");
      window.removeEventListener("pointermove", move);
      cancelAnimationFrame(raf);
    };
  }, [onDash]);

  if (!onDash) return null;
  return (
    <>
      <div ref={ring} className="cursor-ring" />
      <div ref={dot} className="cursor-dot" />
    </>
  );
}
