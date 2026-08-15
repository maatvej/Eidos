/**
 * Vitest & React Testing Library setup configuration.
 * Configures DOM matchers, media element stubs, clipboard, and browser APIs for jsdom.
 */

import * as matchers from "@testing-library/jest-dom/matchers";
import { expect, afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

expect.extend(matchers);

// Automatic cleanup after each test run
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

// Mock window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock HTMLMediaElement methods and properties
window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
window.HTMLMediaElement.prototype.pause = vi.fn();
window.HTMLMediaElement.prototype.load = vi.fn();

// Mock navigator.clipboard
Object.defineProperty(navigator, "clipboard", {
  writable: true,
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(""),
  },
});

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((e: { data: string }) => void)[]> = {};

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, cb: (e: { data: string }) => void) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(cb);
  }

  removeEventListener(event: string, cb: (e: { data: string }) => void) {
    if (!this.listeners[event]) return;
    this.listeners[event] = this.listeners[event].filter((item) => item !== cb);
  }

  emit(event: string, data: string) {
    const handlers = this.listeners[event] || [];
    handlers.forEach((h) => h({ data }));
  }

  close = vi.fn();
}

Object.defineProperty(window, "EventSource", {
  writable: true,
  value: MockEventSource,
});
