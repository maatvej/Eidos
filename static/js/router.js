// filename: static/js/router.js
/**
 * Zero-Framework Client-Side Router for Vanilla JS (ES6+).
 * Features:
 * - HTML5 History API synchronization (pushState, replaceState, popstate)
 * - Dynamic route parameter extraction (/jobs/:jobId, /account/:tab)
 * - Query string parsing and serialization (URLSearchParams)
 * - Event delegation for seamless intercepting of <a data-link> navigation
 * - Session and LocalStorage state persistence and recovery
 * - Lifecycle hooks (beforeEach, afterEach) and document title management
 */

export class Router {
  /**
   * Initializes Router instance with empty routes and hooks.
   */
  constructor() {
    this.routes = [];
    this.beforeHooks = [];
    this.afterHooks = [];
    this.notFoundHandler = null;
    this.currentRoute = null;
    this.isInitialized = false;

    this.handlePopState = this.handlePopState.bind(this);
    this.handleLinkClick = this.handleLinkClick.bind(this);
  }

  /**
   * Registers a fallback handler when no registered route matches.
   * @param {Function} handler - Callback receiving (pathname, routeContext)
   * @returns {Router}
   */
  setNotFoundHandler(handler) {
    this.notFoundHandler = handler;
    return this;
  }

  /**
   * Registers a URL route pattern with associated handler.
   * @param {string} pattern - Route path pattern (e.g. "/", "/jobs/:jobId", "/account/:tab")
   * @param {Function} handler - Callback function receiving ({ params, queryParams, route, state })
   * @param {Object} options - Route metadata (title, defaultParams, etc.)
   * @returns {Router}
   */
  addRoute(pattern, handler, options = {}) {
    const paramNames = [];
    const normalizedPattern = pattern.startsWith("/") ? pattern : `/${pattern}`;

    // Convert route pattern to regex: /jobs/:jobId -> /jobs/([^/]+)
    const regexPattern = normalizedPattern
      .replace(/:([a-zA-Z0-9_]+)/g, (_, paramName) => {
        paramNames.push(paramName);
        return "([^/]+)";
      })
      .replace(/\*/g, "(.*)");

    const regex = new RegExp(`^${regexPattern}$`);

    this.routes.push({
      pattern: normalizedPattern,
      regex,
      paramNames,
      handler,
      options,
    });

    return this;
  }

  /**
   * Registers a global navigation guard before route transition.
   * @param {Function} hook - Callback receiving (toRoute, fromRoute, next)
   */
  beforeEach(hook) {
    if (typeof hook === "function") {
      this.beforeHooks.push(hook);
    }
    return this;
  }

  /**
   * Registers a callback after route transition completes.
   * @param {Function} hook - Callback receiving (toRoute, fromRoute)
   */
  afterEach(hook) {
    if (typeof hook === "function") {
      this.afterHooks.push(hook);
    }
    return this;
  }

  /**
   * Parses query parameters from URL search string or URL object.
   * @param {string|URLSearchParams} search
   * @returns {Record<string, string>}
   */
  parseQueryParams(search) {
    const params = new URLSearchParams(search);
    const result = {};
    for (const [key, value] of params.entries()) {
      result[key] = value;
    }
    return result;
  }

  /**
   * Serializes an object into a URL query string.
   * @param {Record<string, any>} queryObj
   * @returns {string}
   */
  serializeQueryParams(queryObj) {
    if (!queryObj || typeof queryObj !== "object") return "";
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(queryObj)) {
      if (value !== null && value !== undefined && value !== "") {
        params.set(key, String(value));
      }
    }
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }

  /**
   * Matches a given pathname against registered routes.
   * @param {string} pathname
   * @returns {{ route: Object, params: Record<string, string> } | null}
   */
  matchRoute(pathname) {
    const cleanPath = pathname.split("?")[0].split("#")[0] || "/";
    const normalized = cleanPath.length > 1 && cleanPath.endsWith("/")
      ? cleanPath.slice(0, -1)
      : cleanPath;

    for (const route of this.routes) {
      const match = normalized.match(route.regex);
      if (match) {
        const params = {};
        route.paramNames.forEach((name, index) => {
          params[name] = decodeURIComponent(match[index + 1]);
        });
        return { route, params };
      }
    }

    return null;
  }

  /**
   * Navigates to a target URL, updating browser History API and invoking route handlers.
   * @param {string} url - Target URL path and optional query string
   * @param {Object} options - Navigation options
   * @param {boolean} options.replace - Whether to use history.replaceState instead of pushState
   * @param {Object} options.state - State object to store in history
   * @param {boolean} options.silent - If true, updates URL without triggering route handler
   * @returns {Promise<boolean>}
   */
  async navigate(url, { replace = false, state = {}, silent = false } = {}) {
    if (!url) return false;

    // Normalize relative or absolute URL
    let targetPath = url;
    if (targetPath.startsWith(window.location.origin)) {
      targetPath = targetPath.slice(window.location.origin.length);
    }
    if (!targetPath.startsWith("/")) {
      targetPath = `/${targetPath}`;
    }

    const [pathname, searchString] = targetPath.split("?");
    const queryParams = this.parseQueryParams(searchString ? `?${searchString}` : "");
    const match = this.matchRoute(pathname);

    const toRoute = {
      path: pathname,
      fullUrl: targetPath,
      params: match ? match.params : {},
      queryParams,
      state,
      pattern: match ? match.route.pattern : null,
      options: match ? match.route.options : {},
    };

    const fromRoute = this.currentRoute;

    // Run beforeEach guards
    for (const hook of this.beforeHooks) {
      let allow = true;
      let redirectTarget = null;

      await new Promise((resolve) => {
        hook(toRoute, fromRoute, (result) => {
          if (typeof result === "string") {
            redirectTarget = result;
            allow = false;
          } else if (result === false) {
            allow = false;
          }
          resolve();
        });
      });

      if (!allow) {
        if (redirectTarget) {
          return this.navigate(redirectTarget, { replace: true });
        }
        return false;
      }
    }

    // Update History API
    if (!silent) {
      if (replace) {
        window.history.replaceState(state, "", targetPath);
      } else {
        window.history.pushState(state, "", targetPath);
      }
    }

    // Persist current route in session & local storage
    try {
      sessionStorage.setItem("eidos_last_route", targetPath);
      localStorage.setItem("eidos_last_route", targetPath);
    } catch (e) {
      // Storage unavailable or disabled
    }

    this.currentRoute = toRoute;

    // Update Document Title if configured
    if (toRoute.options && toRoute.options.title) {
      document.title = typeof toRoute.options.title === "function"
        ? toRoute.options.title(toRoute)
        : toRoute.options.title;
    }

    // Execute route handler or fallback notFound handler
    if (!silent) {
      if (match) {
        try {
          await match.route.handler(toRoute);
        } catch (err) {
          console.error(`[Router] Error executing handler for ${pathname}:`, err);
        }
      } else if (this.notFoundHandler) {
        try {
          await this.notFoundHandler(pathname, toRoute);
        } catch (err) {
          console.error(`[Router] Error executing notFoundHandler for ${pathname}:`, err);
        }
      }
    }

    // Run afterEach hooks
    for (const hook of this.afterHooks) {
      try {
        hook(toRoute, fromRoute);
      } catch (err) {
        console.error("[Router] Error in afterEach hook:", err);
      }
    }

    // Dispatch global custom event for components listening to route changes
    window.dispatchEvent(
      new CustomEvent("eidos:routechange", {
        detail: { to: toRoute, from: fromRoute },
      })
    );

    return true;
  }

  /**
   * Shorthand to replace current URL in history.
   * @param {string} url
   * @param {Object} options
   */
  replace(url, options = {}) {
    return this.navigate(url, { ...options, replace: true });
  }

  /**
   * Updates only query parameters for current URL without triggering a full view re-render.
   * @param {Record<string, any>} newQueryParams
   * @param {Object} options
   * @param {boolean} options.replace
   * @param {boolean} options.triggerHandler
   */
  async updateQueryParams(newQueryParams = {}, { replace = true, triggerHandler = false } = {}) {
    const current = this.getCurrentRoute();
    const mergedQuery = { ...current.queryParams, ...newQueryParams };

    // Clean null / undefined values
    for (const key of Object.keys(mergedQuery)) {
      if (mergedQuery[key] === null || mergedQuery[key] === undefined || mergedQuery[key] === "") {
        delete mergedQuery[key];
      }
    }

    const qs = this.serializeQueryParams(mergedQuery);
    const targetUrl = `${current.path}${qs}`;

    if (replace) {
      window.history.replaceState(window.history.state || {}, "", targetUrl);
    } else {
      window.history.pushState(window.history.state || {}, "", targetUrl);
    }

    this.currentRoute = {
      ...this.currentRoute,
      fullUrl: targetUrl,
      queryParams: mergedQuery,
    };

    try {
      sessionStorage.setItem("eidos_last_route", targetUrl);
    } catch (e) {}

    if (triggerHandler) {
      const match = this.matchRoute(current.path);
      if (match) {
        await match.route.handler(this.currentRoute);
      }
    }

    window.dispatchEvent(
      new CustomEvent("eidos:querychange", {
        detail: { queryParams: mergedQuery, fullUrl: targetUrl },
      })
    );
  }

  /**
   * Returns current active route details.
   * @returns {{ path: string, fullUrl: string, params: Record<string, string>, queryParams: Record<string, string>, state: any }}
   */
  getCurrentRoute() {
    if (this.currentRoute) {
      return this.currentRoute;
    }

    const fullUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const [pathname, search] = fullUrl.split("?");
    const queryParams = this.parseQueryParams(search ? `?${search}` : "");
    const match = this.matchRoute(pathname);

    return {
      path: pathname,
      fullUrl,
      params: match ? match.params : {},
      queryParams,
      state: window.history.state || {},
    };
  }

  /**
   * Handles popstate event triggered by browser Back/Forward buttons.
   * @param {PopStateEvent} event
   */
  handlePopState(event) {
    const fullUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    this.navigate(fullUrl, { replace: true, state: event.state || {}, silent: false });
  }

  /**
   * Event delegation interceptor for internal links.
   * Intercepts clicks on elements with [data-link] or standard internal relative links.
   * @param {MouseEvent} event
   */
  handleLinkClick(event) {
    // Check if modifier keys are pressed (e.g. Ctrl/Cmd for open in new tab)
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey
    ) {
      return;
    }

    const anchor = event.target.closest("a");
    if (!anchor) return;

    // Check if anchor is an internal SPA link
    const hasDataLink = anchor.hasAttribute("data-link");
    const href = anchor.getAttribute("href");

    if (!href || href.startsWith("#") || href.startsWith("javascript:") || href.startsWith("mailto:")) {
      return;
    }

    // If explicit download or external target, ignore
    if (anchor.hasAttribute("download") || anchor.getAttribute("target") === "_blank") {
      return;
    }

    // Check if link points to Django Allauth accounts or Django Admin or file downloads
    if (
      href.startsWith("/accounts/") ||
      href.startsWith("/admin/") ||
      href.startsWith("/api/") ||
      href.includes("/export?")
    ) {
      return;
    }

    const isSameOrigin = anchor.origin === window.location.origin;
    if (hasDataLink || (isSameOrigin && !href.startsWith("http"))) {
      event.preventDefault();
      const targetUrl = anchor.pathname + anchor.search + anchor.hash;
      this.navigate(targetUrl);
    }
  }

  /**
   * Initializes router listeners and hydrates initial page route.
   */
  init() {
    if (this.isInitialized) return;
    this.isInitialized = true;

    window.addEventListener("popstate", this.handlePopState);
    document.addEventListener("click", this.handleLinkClick);

    // Initial Route Hydration - immediately resolve current browser location on load
    const triggerInitialRoute = () => {
      const initialUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      this.navigate(initialUrl, { replace: true });
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", triggerInitialRoute, { once: true });
    } else {
      triggerInitialRoute();
    }
  }

  /**
   * Cleans up event listeners when needed.
   */
  destroy() {
    window.removeEventListener("popstate", this.handlePopState);
    document.removeEventListener("click", this.handleLinkClick);
    this.isInitialized = false;
  }
}

// Global Single Instance Export
export const router = new Router();
