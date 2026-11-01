// Lazy mock — 只在用到时 mock,避免空 mock 失败
import "@testing-library/jest-dom";

// ResizeObserver mock(TradingView Lightweight Charts 用)
if (typeof global.ResizeObserver === "undefined") {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as any;
}

// matchMedia mock
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    media: "",
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as any;
}