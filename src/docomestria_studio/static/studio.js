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
  let viewport = null;
  let renderTask = null;
  let initialized = false;

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
    canvasWidth: 0,
    canvasHeight: 0,
    pdfScale: 1.5,

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
      const canvas = this.$refs.pdfCanvas;
      const container = canvas.parentElement;
      // Fit viewport to container width (account for ~16px padding/scrollbar).
      const baseViewport = page.getViewport({ scale: 1 });
      const targetWidth = Math.max(200, (container?.clientWidth || 600) - 16);
      this.pdfScale = targetWidth / baseViewport.width;
      viewport = page.getViewport({ scale: this.pdfScale });
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      this.canvasWidth = viewport.width;
      this.canvasHeight = viewport.height;
      renderTask = page.render({ canvasContext: ctx, viewport: viewport });
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
      if (!this.step || !viewport) return;
      const color = this.step.engine_color || "#6b7280";
      const bboxes = (this.step.bboxes || []).filter(
        (b) => !b.page || b.page === this.currentPage
      );
      for (const bbox of bboxes) {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", String(bbox.x * this.pdfScale));
        rect.setAttribute("y", String(bbox.y * this.pdfScale));
        rect.setAttribute("width", String(bbox.w * this.pdfScale));
        rect.setAttribute("height", String(bbox.h * this.pdfScale));
        rect.setAttribute("fill", color);
        rect.setAttribute("fill-opacity", "0.18");
        rect.setAttribute("stroke", color);
        rect.setAttribute("stroke-width", "1.2");
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
