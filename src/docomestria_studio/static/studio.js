/**
 * studioApp — Alpine.js component that drives the studio viewer.
 *
 * Responsibilities:
 *   - Poll /api/session/<id>/status while the pipeline is running.
 *   - Once ready, fetch each step on demand via /api/session/<id>/step/<i>.
 *   - Render the PDF page via pdf.js and overlay the current step's bboxes
 *     as SVG rects colored by engine.
 *   - Provide Next / Back / Auto / Skip controls.
 */
function studioApp(sessionId) {
  // Kept OUT of reactive state: pdf.js objects use private class fields
  // that throw when accessed through Alpine's reactive Proxy.
  let pdfDoc = null;
  let renderTask = null;
  let initialized = false;
  // Intrinsic render scale — keeps the canvas sharp on hi-DPI. CSS scales the
  // canvas to fit the panel, and the SVG overlay uses a viewBox in PDF points
  // so bboxes line up regardless of display size.
  const INTRINSIC_SCALE = 2.0;

  return {
    sessionId,
    status: "processing",
    stepsDone: 0,
    stepsTotal: 0,
    errorMessage: "",

    steps: [],            // cached step JSON, indexed
    currentIndex: 0,
    step: null,
    autoMode: false,
    autoTimer: null,

    currentPage: 1,
    totalPages: 1,
    pageWidthPts: 0,      // PDF page width in points — drives SVG viewBox
    pageHeightPts: 0,

    init() {
      if (initialized) return;
      initialized = true;
      this.loadPdf();
      this.pollStatus();
    },

    async loadPdf() {
      try {
        const loadingTask = window.pdfjsLib.getDocument(
          `/api/session/${this.sessionId}/pdf`
        );
        pdfDoc = await loadingTask.promise;
        this.totalPages = pdfDoc.numPages;
        await this.renderPage(1);
      } catch (err) {
        console.error("PDF load failed:", err);
      }
    },

    async renderPage(pageNum) {
      if (!pdfDoc) return;
      if (renderTask) {
        try { renderTask.cancel(); } catch (e) { /* ignore */ }
      }
      const page = await pdfDoc.getPage(pageNum);
      // Page dimensions in PDF points (scale=1 -> 1 CSS px == 1 pt).
      const pageVp = page.getViewport({ scale: 1 });
      this.pageWidthPts = pageVp.width;
      this.pageHeightPts = pageVp.height;
      // Render to a fixed intrinsic resolution. CSS will scale the canvas
      // display size to fit the panel via `width: 100%` on the canvas.
      const renderVp = page.getViewport({ scale: INTRINSIC_SCALE });
      const canvas = this.$refs.pdfCanvas;
      const ctx = canvas.getContext("2d");
      canvas.width = renderVp.width;
      canvas.height = renderVp.height;
      renderTask = page.render({ canvasContext: ctx, viewport: renderVp });
      try {
        await renderTask.promise;
      } catch (e) {
        if (e?.name !== "RenderingCancelledException") throw e;
        return;
      } finally {
        renderTask = null;
      }
      this.currentPage = pageNum;
      this.drawOverlay();
    },

    prevPage() {
      if (this.currentPage > 1) this.renderPage(this.currentPage - 1);
    },

    nextPage() {
      if (this.currentPage < this.totalPages) this.renderPage(this.currentPage + 1);
    },

    async pollStatus() {
      while (this.status === "processing") {
        try {
          const res = await fetch(`/api/session/${this.sessionId}/status`);
          if (!res.ok) {
            this.status = "error";
            this.errorMessage = `HTTP ${res.status}`;
            return;
          }
          const data = await res.json();
          this.status = data.status;
          this.stepsDone = data.steps_done;
          this.stepsTotal = data.steps_total;
          if (data.status === "error") {
            this.errorMessage = data.error || "Unknown error";
            return;
          }
          if (data.status === "ready") {
            await this.loadStep(0);
            return;
          }
        } catch (err) {
          this.status = "error";
          this.errorMessage = String(err);
          return;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
    },

    async loadStep(index) {
      if (index < 0) return;
      if (this.steps[index]) {
        this.step = this.steps[index];
        this.currentIndex = index;
        this.drawOverlay();
        return;
      }
      const res = await fetch(`/api/session/${this.sessionId}/step/${index}`);
      if (!res.ok) return;
      const data = await res.json();
      this.steps[index] = data;
      this.step = data;
      this.currentIndex = index;
      this.drawOverlay();
    },

    next() {
      if (this.currentIndex < this.stepsDone - 1) {
        this.loadStep(this.currentIndex + 1);
      }
    },

    back() {
      if (this.currentIndex > 0) this.loadStep(this.currentIndex - 1);
    },

    skip() {
      const last = this.stepsDone - 1;
      if (last > this.currentIndex) this.loadStep(last);
    },

    toggleAuto() {
      this.autoMode = !this.autoMode;
      if (this.autoMode) {
        this.autoTimer = setInterval(() => {
          if (this.step && this.currentIndex >= this.stepsDone - 1) {
            this.toggleAuto();
            return;
          }
          this.next();
        }, 1500);
      } else if (this.autoTimer) {
        clearInterval(this.autoTimer);
        this.autoTimer = null;
      }
    },

    drawOverlay() {
      const svg = this.$refs.overlay;
      if (!svg) return;
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      if (!this.step || !this.pageWidthPts) return;
      const color = this.step.engine_color || "#6b7280";
      const bboxes = (this.step.bboxes || []).filter(
        (b) => !b.page || b.page === this.currentPage
      );
      // Bbox coords are in PDF points (top-left origin); the SVG viewBox is
      // set to (0 0 pageWidthPts pageHeightPts) so we can use raw PDF units
      // directly. The browser handles all display scaling for us.
      const strokeW = Math.max(0.6, this.pageWidthPts / 600);
      for (const bbox of bboxes) {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", String(bbox.x));
        rect.setAttribute("y", String(bbox.y));
        rect.setAttribute("width", String(bbox.w));
        rect.setAttribute("height", String(bbox.h));
        rect.setAttribute("fill", color);
        rect.setAttribute("fill-opacity", "0.18");
        rect.setAttribute("stroke", color);
        rect.setAttribute("stroke-width", String(strokeW));
        if (bbox.label) {
          const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
          title.textContent = bbox.label;
          rect.appendChild(title);
        }
        svg.appendChild(rect);
      }
    },

    formatValue(value) {
      if (value === null || value === undefined) return "";
      if (typeof value === "object") {
        try {
          return JSON.stringify(value);
        } catch (e) {
          return String(value);
        }
      }
      const s = String(value);
      return s.length > 80 ? s.slice(0, 80) + "..." : s;
    },
  };
}

// Expose for Alpine x-data resolution.
window.studioApp = studioApp;
