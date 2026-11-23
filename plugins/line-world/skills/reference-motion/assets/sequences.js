/* Reusable interview edit. Load after motion.js and call with scene-relative seconds. */
(() => {
  "use strict";
  const M = globalThis.LineWorldMotion;
  const unit = value => Math.max(0, Math.min(1, value));

  function interviewOpen(ctx, time, content, options = {}) {
    const w = options.width || ctx.canvas.width, h = options.height || ctx.canvas.height;
    const style = M.resolveTheme(ctx,options), reference = options.mode === "reference";
    // A reference edit keeps the measured 24 fps cues. The default gives each
    // transition its own hold and lets the identifier survive the camera cut.
    const cues = reference
      ? {open:3.5,openDuration:.375,interview:5.25,interviewDuration:.417,name:5.5,wide:9.2083}
      : {open:2.1,openDuration:1.35,interview:6.2,interviewDuration:1.4,name:7.65,wide:12.0};
    const solid = color => (layer, width, height) => {
      layer.fillStyle = color;
      layer.fillRect(0, 0, width, height);
    };
    const slate = (layer, width, height) => {
      solid(style.paper)(layer, width, height);
      // Collapse the outgoing badge independently of the next circular reveal.
      const scale = reference ? 1-unit((time-3.0833)/.4167)**1.5 : 1;
      if (scale > 0 && content.mark) {
        const size = height * .425 * scale;
        M.media(layer,content.mark,(width-size)/2,(height-size)/2,size,size);
      }
    };
    const title = (layer, width, height) => {
      solid(reference?style.accent:style.paper)(layer,width,height);
      layer.save();
      if (reference) layer.globalAlpha *= unit((time - 3.76) / .35);
      layer.fillStyle = reference?style.light:style.ink;
      layer.font = "600 " + height*.082 + "px " + style.font;
      layer.textAlign = "center"; layer.textBaseline = "middle";
      layer.fillText(content.title || "", width/2, height/2, width*.86);
      layer.restore();
    };
    if (time < cues.open) M.media(ctx,slate,0,0,w,h);
    else if (time < cues.interview) M.transition(ctx,"iris-fill",(time-cues.open)/cues.openDuration,slate,title,options);
    else if (time < cues.interview+cues.interviewDuration) M.transition(ctx,"dissolve",(time-cues.interview)/cues.interviewDuration,title,content.close,options);
    else M.media(ctx,time<cues.wide?content.close:content.wide,0,0,w,h);
    const labelTime=time-cues.name, exitAt=reference?7.12:6.75;
    if (labelTime >= 0 && labelTime < exitAt+1.13) {
      M.artifact(ctx,"speaker-id",labelTime,{title:content.name,detail:content.role,side:content.side,exitAt,exitDuration:1.13},options);
    }
  }

  function interviewClose(ctx, time, content, options = {}) {
    const w = options.width || ctx.canvas.width, h = options.height || ctx.canvas.height;
    const style = M.resolveTheme(ctx,options), seam = options.y ?? 150/360;
    const duration = options.duration ?? (options.mode==="reference"?.75:1.45);
    const end = (layer, width, height) => {
      layer.fillStyle = style.light; layer.fillRect(0,0,width,height);
    };
    M.transition(ctx,"shutter-close",time/duration,content.wide,end,{...options,y:seam});
    // The mark overlays both moving panels while the last slit is still visible.
    const size = .467*h*unit((time/duration-.6667)/.6133);
    if (size && content.mark) M.media(ctx,content.mark,(w-size)/2,seam*h-size/2,size,size);
  }

  globalThis.LineWorldSequences = Object.freeze({interviewOpen,interviewClose});
})();
