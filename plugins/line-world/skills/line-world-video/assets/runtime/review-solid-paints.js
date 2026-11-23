/* Inspect authored paints before capture without interpreting source-image pixels. */
(() => {
  "use strict";
  if (window.lineWorldPaintReview) return;

  const svgNamespace = "http://www.w3.org/2000/svg";
  const svgGeometry = new Set(["circle", "ellipse", "line", "path", "polygon", "polyline", "rect", "text", "textPath", "tspan", "use"]);
  const mediaElements = new Set(["audio", "canvas", "embed", "iframe", "img", "image", "object", "picture", "video"]);
  const cssGradient = /\b(?:repeating-)?(?:linear|radial|conic)-gradient\(/i;
  const canvasStates = new WeakMap();
  const contextKinds = new WeakMap();
  let frame = null;

  function alpha(color) {
    if (typeof color !== "string") return 1;
    if (color === "transparent" || color === "none") return 0;
    if (/^#[\da-f]{4}$|^#[\da-f]{8}$/i.test(color)) {
      const hex = color.length === 5 ? color.at(-1).repeat(2) : color.slice(-2);
      return parseInt(hex, 16) / 255;
    }
    const part = color.match(/\/\s*([\d.]+%?)\s*\)$/)?.[1] ??
      color.match(/^(?:rgba|hsla)\([^)]*,\s*([\d.]+%?)\s*\)$/i)?.[1];
    return part === undefined ? 1 : parseFloat(part) / (part.endsWith("%") ? 100 : 1);
  }

  const partial = n => n > 0 && n < 1;
  const kind = (map, name, detail, target) => map.set(
    JSON.stringify([name, target, detail]), {kind: name, target, detail},
  );
  const targetName = element => element.id ? "#" + element.id :
    element.localName + (element.hasAttribute("data-export-surface") ? "[data-export-surface]" : "");

  function localReference(value, owner) {
    try {
      const url = new URL(value, owner.baseURI);
      const id = decodeURIComponent(url.hash.slice(1));
      url.hash = "";
      const source = new URL(owner.ownerDocument.URL);
      source.hash = "";
      return id && url.href === source.href ? owner.ownerDocument.getElementById(id) : null;
    } catch {
      return null;
    }
  }

  const urls = value => [...(value || "").matchAll(/url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*))\s*\)/gi)]
    .map(match => (match[1] ?? match[2] ?? match[3]).trim());

  // Ignore number tokens in color functions when reading computed shadow lengths.
  const withoutColors = value => value.replace(/[a-z][\w-]*\([^()]*\)/gi, "");
  const px = value => [...withoutColors(value).matchAll(/(-?[\d.]+)px\b/gi)].map(match => Number(match[1]));
  const softShadow = value => {
    const layers = (value || "").match(/(?:[^,(]+|\([^)]*\))+/g) || [];
    return layers.some(layer => (px(layer)[2] ?? 0) > 0 &&
      ![...layer.matchAll(/(?:rgba?|hsla?|color)\([^)]*\)/gi)].some(match => alpha(match[0]) === 0));
  };

  function filterEffects(value, owner) {
    const effects = [];
    if ([...(value || "").matchAll(/\bblur\(\s*([\d.]+)px\s*\)/gi)].some(match => Number(match[1]) > 0))
      effects.push("filter");
    if (/drop-shadow\(/i.test(value) && softShadow(value.slice(value.indexOf("drop-shadow(") + 12)))
      effects.push("shadow");
    for (const url of urls(value)) {
      const filter = owner && localReference(url, owner);
      if (filter?.localName !== "filter") continue;
      for (const node of filter.querySelectorAll("feGaussianBlur, feDropShadow")) {
        if (node.localName === "feDropShadow") {
          const style = getComputedStyle(node);
          if (Number(style.floodOpacity) === 0 || alpha(style.floodColor) === 0) continue;
        }
        if ((node.getAttribute("stdDeviation") || "").split(/[\s,]+/).some(n => Number(n) > 0))
          effects.push(node.localName === "feDropShadow" ? "shadow" : "filter");
      }
    }
    return effects;
  }

  const filterAlpha = value => [...(value || "").matchAll(/\bopacity\(\s*([\d.]+)(%)?\s*\)/gi)]
    .reduce((current, match) => current * Math.min(1, Number(match[1]) / (match[2] ? 100 : 1)), 1);

  function canvasState(canvas) {
    let state = canvasStates.get(canvas);
    if (!state || state.width !== canvas.width || state.height !== canvas.height) {
      state = {width: canvas.width, height: canvas.height, findings: new Map(), clipped: false, stack: []};
      canvasStates.set(canvas, state);
    }
    return state;
  }

  function coversCanvas(ctx, state, [x, y, w, h]) {
    if (state.clipped || ![x, y, w, h].every(Number.isFinite)) return false;
    const t = ctx.getTransform();
    if (t.b !== 0 || t.c !== 0) return false;
    const l = x * t.a + t.e, r = (x + w) * t.a + t.e;
    const top = y * t.d + t.f, bottom = (y + h) * t.d + t.f;
    return Math.min(l, r) <= 0 && Math.min(top, bottom) <= 0 &&
      Math.max(l, r) >= state.width && Math.max(top, bottom) >= state.height;
  }

  function observePaint(ctx, operation, args) {
    const state = canvasState(ctx.canvas);
    const paint = operation.startsWith("stroke") ? ctx.strokeStyle : ctx.fillStyle;
    const colorAlpha = alpha(paint), opacity = ctx.globalAlpha * filterAlpha(ctx.filter);
    if (opacity === 0 || colorAlpha === 0 || ctx.globalCompositeOperation === "destination-out") return;
    if (operation.endsWith("Text") && !String(args[0] ?? "").trim()) return;
    if (operation.endsWith("Rect") && (!Number(args[2]) || !Number(args[3]))) return;
    if (state.findings.size && operation === "fillRect" && typeof paint === "string" &&
        opacity === 1 && colorAlpha === 1 && ctx.filter === "none" &&
        ctx.globalCompositeOperation === "source-over" && coversCanvas(ctx, state, args)) state.findings.clear();

    const target = ctx.canvas instanceof HTMLCanvasElement ? targetName(ctx.canvas) : "offscreen-canvas";
    const record = (name, property) => kind(state.findings, name, operation + " " + property, target);
    if (paint instanceof CanvasGradient) record("gradient", "uses a CanvasGradient");
    if (paint instanceof CanvasPattern) record("pattern", "uses a CanvasPattern");
    if (partial(opacity) || partial(colorAlpha)) record("opacity", "uses partial paint alpha");
    if (ctx.shadowBlur > 0 && alpha(ctx.shadowColor) > 0) record("shadow", "uses shadowBlur");
    if (ctx.filter && ctx.filter !== "none")
      for (const effect of filterEffects(ctx.filter, ctx.canvas)) record(effect, "uses " + ctx.filter);
  }

  function wrap(prototype, name, observe) {
    const method = Object.getOwnPropertyDescriptor(prototype, name);
    if (!method?.value) return;
    const original = method.value;
    Object.defineProperty(prototype, name, {...method, value: function (...args) {
      const value = original.apply(this, args);
      observe(this, args, value);
      return value;
    }});
  }

  for (const Canvas of [window.HTMLCanvasElement, window.OffscreenCanvas].filter(Boolean)) {
    wrap(Canvas.prototype, "getContext", (canvas, args, result) => {
      if (result) contextKinds.set(canvas, String(args[0]));
    });
    for (const size of ["width", "height"]) {
      const descriptor = Object.getOwnPropertyDescriptor(Canvas.prototype, size);
      if (!descriptor?.set) continue;
      Object.defineProperty(Canvas.prototype, size, {...descriptor, set(value) {
        descriptor.set.call(this, value);
        canvasStates.delete(this);
      }});
    }
  }

  for (const Context of [window.CanvasRenderingContext2D, window.OffscreenCanvasRenderingContext2D].filter(Boolean)) {
    const prototype = Context.prototype;
    for (const name of ["fill", "stroke", "fillRect", "strokeRect", "fillText", "strokeText"])
      wrap(prototype, name, (ctx, args) => observePaint(ctx, name, args));
    wrap(prototype, "save", ctx => { const s = canvasState(ctx.canvas); s.stack.push(s.clipped); });
    wrap(prototype, "restore", ctx => { const s = canvasState(ctx.canvas); if (s.stack.length) s.clipped = s.stack.pop(); });
    wrap(prototype, "clip", ctx => { canvasState(ctx.canvas).clipped = true; });
    wrap(prototype, "reset", ctx => { canvasStates.delete(ctx.canvas); });
    wrap(prototype, "clearRect", (ctx, args) => {
      const state = canvasState(ctx.canvas);
      if (state.findings.size && coversCanvas(ctx, state, args)) state.findings.clear();
    });
    // Media pixels remain untouched. Canvas-to-canvas copies carry only our own source observations.
    wrap(prototype, "drawImage", (ctx, [source]) => {
      const from = canvasStates.get(source);
      if (!from?.findings.size || ctx.globalAlpha === 0) return;
      const to = canvasState(ctx.canvas);
      for (const [key, detail] of from.findings) to.findings.set(key, detail);
    });
  }

  function inspectDom(findings, covered) {
    const styles = new Map(), styleOf = element => {
      if (!styles.has(element)) styles.set(element, getComputedStyle(element));
      return styles.get(element);
    };
    const ancestors = element => {
      const lineage = [];
      for (let node = element; node; node = node.parentElement) lineage.push(node);
      return lineage;
    };
    const hidden = style => style.display === "none" || style.contentVisibility === "hidden" ||
      Number(style.opacity) === 0 || filterAlpha(style.filter) === 0;
    const inView = (element, style, parents) => {
      if (style.visibility !== "visible" || parents.some(node => hidden(styleOf(node)))) return false;
      if (!element.getClientRects().length) return false;
      const b = element.getBoundingClientRect();
      const stroke = parseFloat(style.strokeWidth);
      const pad = element.namespaceURI === svgNamespace && style.stroke !== "none" && Number.isFinite(stroke) ? stroke / 2 : 0;
      if (!(b.width || b.height || pad) || b.right + pad <= 0 || b.bottom + pad <= 0 || b.left - pad >= innerWidth || b.top - pad >= innerHeight) return false;
      return !parents.slice(1).some(node => {
        const parentStyle = styleOf(node);
        const clips = [parentStyle.overflowX, parentStyle.overflowY].map(v => /^(?:auto|hidden|scroll|clip)$/.test(v));
        if (!clips.some(Boolean) || node.namespaceURI === svgNamespace) return false;
        const p = node.getBoundingClientRect();
        return (clips[0] && (b.right + pad <= p.left || b.left - pad >= p.right)) ||
          (clips[1] && (b.bottom + pad <= p.top || b.top - pad >= p.bottom));
      });
    };
    const directText = element => [...element.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    const inspectStyle = (element, style, parents, target, text, vector, forcedBox = false) => {
      const record = (name, detail, label = target) => kind(findings, name, detail, label);
      const color = (value, property) => {
        if (partial(alpha(value))) record("opacity", property + " uses partial paint alpha");
        for (const url of urls(value)) {
          const reference = localReference(url, element);
          if (reference?.localName === "pattern") record("pattern", property + " references " + url);
          if (reference && /^(?:linear|radial)Gradient$/.test(reference.localName))
            record("gradient", property + " references " + url);
        }
      };
      const gradient = property => {
        if (cssGradient.test(style[property] || "")) record("gradient", property + " uses a CSS gradient");
      };
      const border = ["Top", "Right", "Bottom", "Left"].filter(side =>
        parseFloat(style["border" + side + "Width"]) > 0 && !["none", "hidden"].includes(style["border" + side + "Style"]));
      const hasBox = forcedBox || alpha(style.backgroundColor) > 0 || cssGradient.test(style.backgroundImage || "") ||
        border.some(side => alpha(style["border" + side + "Color"]) > 0) || softShadow(style.boxShadow);
      const textColor = style.webkitTextFillColor || style.color;
      const textStroke = parseFloat(style.webkitTextStrokeWidth) > 0 && alpha(style.webkitTextStrokeColor) > 0;
      const textPaint = text && !vector && (alpha(textColor) > 0 || textStroke || softShadow(style.textShadow));
      const vectorPaint = vector ? ["fill", "stroke"].filter(property => {
        if (property === "fill" && element.localName === "line") return false;
        if (property === "stroke" && parseFloat(style.strokeWidth) <= 0) return false;
        return alpha(style[property]) > 0 && Number(style[property + "Opacity"]) > 0;
      }) : [];
      if (!textPaint && !vectorPaint.length && !hasBox) return;
      if (textPaint) {
        color(textColor, "text color");
        if (textStroke) color(style.webkitTextStrokeColor, "text stroke");
      }
      if (text && softShadow(style.textShadow)) record("shadow", "uses diffuse text-shadow");
      for (const property of vectorPaint) {
        color(style[property], property);
        if (partial(Number(style[property + "Opacity"]))) record("opacity", property + " uses partial paint opacity");
      }
      if (hasBox) {
        color(style.backgroundColor, "background-color");
        gradient("backgroundImage");
        if (style.borderImageSource) gradient("borderImageSource");
        for (const side of border) color(style["border" + side + "Color"], "border-" + side.toLowerCase());
        if (softShadow(style.boxShadow)) record("shadow", "uses diffuse box-shadow");
      }
      gradient("maskImage");
      if (/::(?:before|after)$/.test(target)) {
        if (partial(Number(style.opacity) * filterAlpha(style.filter)))
          record("opacity", "uses partial pseudo-element opacity");
        for (const effect of filterEffects(style.filter, element))
          record(effect, "uses " + style.filter);
      }
      for (const node of parents) {
        const ancestorStyle = styleOf(node), label = targetName(node);
        if (partial(Number(ancestorStyle.opacity) * filterAlpha(ancestorStyle.filter)))
          record("opacity", "uses partial composited opacity", label);
        for (const effect of filterEffects(ancestorStyle.filter, node))
          record(effect, "uses " + ancestorStyle.filter, label);
      }
    };
    const skip = "defs, symbol, clipPath, filter, mask, marker, pattern, linearGradient, radialGradient, script, style, template, noscript";
    for (const element of document.querySelectorAll("*")) {
      if (element.closest(skip)) continue;
      const style = styleOf(element), parents = ancestors(element);
      if (!inView(element, style, parents)) continue;
      if (element.localName === "canvas") {
        if (contextKinds.get(element) === "2d") {
          covered.add("canvas-2d");
          for (const [key, finding] of canvasState(element).findings) findings.set(key, finding);
        }
        continue;
      }
      if (mediaElements.has(element.localName)) continue;
      const vector = element.namespaceURI === svgNamespace && svgGeometry.has(element.localName);
      inspectStyle(element, style, parents, targetName(element), directText(element), vector);
      if (element.localName === "use" && vector) {
        const reference = localReference(element.href.baseVal, element);
        if (reference) for (const node of [reference, ...reference.querySelectorAll("*")]) {
          const s = styleOf(node);
          if (svgGeometry.has(node.localName) && !hidden(s) && s.visibility === "visible")
            inspectStyle(node, s, [], targetName(element) + " ↦ " + targetName(node), directText(node), true);
        }
      }
      if (element.namespaceURI !== svgNamespace) for (const pseudo of ["::before", "::after"]) {
        const s = getComputedStyle(element, pseudo);
        if (s.content === "none" || s.content === "normal" || hidden(s) || s.visibility !== "visible") continue;
        inspectStyle(element, s, parents, targetName(element) + pseudo, !/^(['"])\1$|^url\(/.test(s.content), false);
      }
    }
  }

  function inspect() {
    const canvas = document.querySelector("canvas[data-export-surface]");
    if (canvas?.width === innerWidth && canvas?.height === innerHeight) {
      const supported = contextKinds.get(canvas) === "2d";
      return {frame, surface: supported ? "canvas-2d" : "canvas-unsupported",
        covered: supported ? ["canvas-2d"] : [],
        findings: supported ? [...canvasState(canvas).findings.values()] : []};
    }
    const findings = new Map(), covered = new Set(["svg-paint", "css-paint"]);
    inspectDom(findings, covered);
    return {frame, surface: "dom", covered: [...covered], findings: [...findings.values()]};
  }

  window.lineWorldPaintReview = Object.freeze({
    begin(number) { frame = number; },
    inspect,
  });
})();
