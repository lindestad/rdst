import { useCallback, useEffect, useRef, useState } from "react";
import {
  VIEWBOX_H,
  VIEWBOX_W,
  ZOOM_BUTTON_FACTOR,
  ZOOM_MAX,
  ZOOM_MIN,
  ZOOM_WHEEL_FACTOR,
} from "../config";

export { VIEWBOX_H, VIEWBOX_W };

export type MapView = { tx: number; ty: number; k: number };

export type UseMapView = {
  svgRef: React.MutableRefObject<SVGSVGElement | null>;
  view: MapView;
  isPanning: boolean;
  handleMouseDown: (event: React.MouseEvent<SVGSVGElement>) => void;
  handleMouseMove: (event: React.MouseEvent<SVGSVGElement>) => void;
  handleMouseUp: () => void;
  zoomCenter: (factor: number) => void;
  resetView: () => void;
  guardedClick: (handler: () => void) => () => void;
};

export function useMapView(): UseMapView {
  const [view, setView] = useState<MapView>({ tx: 0, ty: 0, k: 1 });
  const [isPanning, setIsPanning] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; tx: number; ty: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);

  const screenToView = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    const matrix = svg.getScreenCTM();
    if (!matrix) return { x: 0, y: 0 };
    const viewPoint = point.matrixTransform(matrix.inverse());
    return { x: viewPoint.x, y: viewPoint.y };
  }, []);

  const zoomAt = useCallback((sx: number, sy: number, factor: number) => {
    setView((prev) => {
      const nextK = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, prev.k * factor));
      if (nextK === prev.k) return prev;
      const worldX = (sx - prev.tx) / prev.k;
      const worldY = (sy - prev.ty) / prev.k;
      return {
        tx: sx - worldX * nextK,
        ty: sy - worldY * nextK,
        k: nextK,
      };
    });
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const { x, y } = screenToView(event.clientX, event.clientY);
      const factor = event.deltaY < 0 ? ZOOM_WHEEL_FACTOR : 1 / ZOOM_WHEEL_FACTOR;
      zoomAt(x, y, factor);
    };
    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
  }, [zoomAt, screenToView]);

  const handleMouseDown = (event: React.MouseEvent<SVGSVGElement>) => {
    if (event.button !== 0) return;
    const start = screenToView(event.clientX, event.clientY);
    dragRef.current = {
      startX: start.x,
      startY: start.y,
      tx: view.tx,
      ty: view.ty,
      moved: false,
    };
    setIsPanning(true);
  };

  const handleMouseMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const current = screenToView(event.clientX, event.clientY);
    const dx = current.x - drag.startX;
    const dy = current.y - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) > 3) {
      drag.moved = true;
    }
    if (drag.moved) {
      setView((prev) => ({ ...prev, tx: drag.tx + dx, ty: drag.ty + dy }));
    }
  };

  const handleMouseUp = () => {
    const drag = dragRef.current;
    if (drag?.moved) {
      suppressClickRef.current = true;
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
    }
    dragRef.current = null;
    setIsPanning(false);
  };

  const resetView = () => setView({ tx: 0, ty: 0, k: 1 });
  const zoomCenter = (factor: number) => zoomAt(VIEWBOX_W / 2, VIEWBOX_H / 2, factor);
  const guardedClick = (handler: () => void) => () => {
    if (suppressClickRef.current) return;
    handler();
  };

  return {
    svgRef,
    view,
    isPanning,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    zoomCenter,
    resetView,
    guardedClick,
  };
}
