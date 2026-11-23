/* Pure parser for fresh CUA AX text. No UI actions, file access or cached indices. */
(function(root){
  function projectIdentity(value) {
    if (typeof value !== 'string') return null;
    const candidate = value.startsWith('docs.google.com/') ? 'https://' + value : value;
    try {
      const url = new URL(candidate);
      const match = url.pathname.match(/^\/videos\/(?:u\/\d+\/)?d\/([\w-]+)\/edit\/?$/);
      if (url.origin !== 'https://docs.google.com' || url.username || url.password || !match) return null;
      const queryScene = url.searchParams.get('scene');
      const hashScene = new URLSearchParams(url.hash.slice(1)).get('scene');
      const sceneId = queryScene && hashScene && queryScene !== hashScene ? null : queryScene || hashScene;
      return {id: match[1], sceneId, url: url.href};
    } catch {
      return null;
    }
  }

  function workingScript(lines) {
    const current = lines.some(line => /^\s*\d+ tab(?: item)? \(selected[^)]*\) Current scene\b/.test(line));
    const scene = lines.map(line => line.match(/^\s*\d+ text Scene (\d+) \/ (\d+)\s*$/)).filter(Boolean);
    const start = lines.findIndex(line => /^\s*\d+ (?:container|group \((?:form|formulario)\)) Scripts\s*$/.test(line));
    if (start < 0) return null;
    const depth = lines[start].match(/^\s*/)[0].length;
    const end = lines.findIndex((line, index) => index > start &&
      /^\s*\d+ /.test(line) && line.match(/^\s*/)[0].length <= depth);
    if (end < 0) return null;
    const content = lines.slice(start + 1, end)
      .map(line => line.match(/^\s*\d+ text (.*)$/)?.[1] || '').filter(Boolean).join(' ');
    const empty = lines.some(line => /^\s*\d+ button \(disabled\) Type your script first\s*$/.test(line));
    if (!empty && !content) return null;
    return {
      order: current && scene.length === 1 ? +scene[0][1] : null,
      count: current && scene.length === 1 ? +scene[0][2] : null,
      text: empty ? '' : content,
    };
  }

  function summarize(ax){
    const lines=String(ax).split('\n');
    const doc = lines.find(line => /^\s*\d+ (?:document|AXWebArea)\b/.test(line));
    const identity = projectIdentity(doc?.match(/(?:Value|URL): (\S+)\s*$/)?.[1]);
    if(!identity)return {recognized:false,reason:'The active document is not a verified Google Vids page.'};
    const controls={};
    const wanted=/^(New scene|Go to beginning|Zoom to fit timeline|Edit script|Insert voiceover|Update voiceover|Update all voiceovers|Generate all voiceovers|Change the voice|Upload\b|Replace video|MP4 video \(\.mp4\)|Export to Drive$|Download$|Export status:|File$|Insert$|Close$)/;
    for(const l of lines){
      const m=l.match(/^\s*(\d+) (?:button|menu item) (.*)/);if(!m)continue;
      const label=m[2].replace(/(?:\((?:botón de activación|toggle button)\)\s*|^Description: )/g,'').split(', ID:')[0].split(' ID:')[0].trim();
      if(!m[2].includes('(disabled)')&&wanted.test(label))controls[label]=+m[1];
    }
    const sceneLines=lines.map(l=>l.match(/^\s*\d+ text (?:Screen reader support enabled\.\s+)?(Scene \d+ of \d+, duration .*)$/)).filter(Boolean);
    const scriptState=workingScript(lines);
    const timers=lines.filter(l=>/^\s*\d+ text \d{2}:\d{2}\.\d/.test(l)).map(l=>l.trim().replace(/^\d+ text /,''));
    const media=[...new Set(lines.flatMap(l=>[...l.matchAll(/(?:Description: |Alt text (?:title|description):\s*)([^\r\n]*?\.(?:mp4|webm|mov))(?=\s|$)/gi)].map(m=>m[1].trim())))];
    const scenes=lines.map(l=>l.match(/^\s*(\d+) button Scene (\d+) of (\d+)\b/)).filter(Boolean).map(m=>({index:+m[1],order:+m[2],total:+m[3]}));
    const complete= scenes.length > 0 && scenes.every((scene, index) => scene.order === index + 1 && scene.total === scenes.length);
    const tabs=Object.fromEntries(lines.map(l=>l.match(/^\s*(\d+) tab(?: item)? .*?(Current scene|All scenes)\b/)).filter(Boolean).map(m=>[m[2],+m[1]]));
    const scene=sceneLines.at(-1)?.[1]||null;
    const focused = lines.map(line=>line.match(/^The focused UI element is \d+ button Scene (\d+) of (\d+)\s*$/)).find(Boolean);
    const selected = scene?.includes('Selected') ? scene.match(/^Scene (\d+) of (\d+),/) : focused;
    const selectedMedia=scene?.match(/Alt text (?:title|description):\s*([^\r\n]*?\.(?:mp4|webm|mov))(?=\s|$)/i)?.[1]?.trim()||null;
    const title=lines.map(line=>line.match(/^\s*(\d+) text field(?: \(settable\))? (?:Description: )?Rename, Value: (.+)$/)).find(Boolean);
    const nativeVoiceover=lines.map(line=>line.match(/^\s*(\d+) checkbox Description: Generate a voiceover, Value: ([01]), ID: content-library-rail-voiceovers-element\s*$/)).find(Boolean);
    if (title) controls.Rename = +title[1];
    if (nativeVoiceover) controls.Voiceover = +nativeVoiceover[1];
    const selectedOrder = selected && +selected[2] === scenes.length ? +selected[1] : null;
    const saveButton=lines.find(line=>/^\s*\d+ (?:button(?: Description:)? Document status: Saved to Drive\.?[, ]+ID: docs-save-indicator-badge|text Document status: Saved to Drive\.?)\s*$/.test(line));
    return {recognized:true,url:identity.url,projectId:identity.id,sceneId:identity.sceneId,saved:Boolean(saveButton),
      title:title?.[2]||null,scene,selectedOrder,selectedMedia,sceneCount:complete?scenes.length:null,
      scenes,tabs,timers,media,script:scriptState?.text||'',scriptState,voiceoverOpen:nativeVoiceover?.[2]==='1',controls};
  }
  // Return one recommendation. The caller executes it with the documented CUA API.
  // Every invocation needs a new full observation; no indices survive an action.
  function uploadNext(input){
    const action=(kind,detail={})=>({kind,...detail});
    if(input.policyStopped)return action('stop',{reason:'Follow the host handoff; do not retry through another transport.'});
    if(input.fullState!==true)return action('read-full-state',{reason:'Diff-only text can omit unchanged controls. Obtain a fresh full AX state.'});
    const state=summarize(input.ax);
    const expected=projectIdentity(input.target?.projectUrl);
    if(!state.recognized||!expected||state.projectId!==expected.id)return action('verify-project',{reason:'Observe the intended Vids project before any upload action.'});
    const phase=input.phase||'select';
    const name=String(input.target?.file||'').split(/[\\/]/).at(-1);
    const order=input.target?.sceneOrder;
    if(!name||!Number.isInteger(order)||order<1)return action('verify-target',{reason:'Supply the exact file and positive scene ordinal from the current queue.'});
    if(phase==='await-dialog'&&input.nativeOpenDialogObserved===true)return action('fill-native-filename',{file:input.target.file,keys:['Alt_L+n','paste exact path','Return'],then:'Observe insertion before any retry. Owned-dialog AX indices may be unavailable.'});
    if(phase==='await-dialog'||phase==='await-insertion'){
      if(state.selectedOrder===order&&state.selectedMedia===name)return action('verify-inserted-scene',{sceneOrder:order,file:name,checks:['Correct replacement pixels','One video object and retained narration','Measured duration, normal speed and current scene count']});
      if(input.foreground===false)return action('foreground-tab',{then:'Observe the intended tab and any native Open dialog; do not click Upload again.'});
      return action('observe-upload-result',{reason:'The dialog or inserted media can appear one observation late. Inspect fresh state/screenshot before retrying.'});
    }
    if(input.foreground!==true)return action('foreground-tab',{then:'Verify the visible intended project and selected scene before opening Upload.'});
    if(state.selectedOrder!==order){
      const target=state.scenes.find(s=>s.order===order);
      return target?action('select-scene',{index:target.index,sceneOrder:order,then:'Read fresh full state and verify selection.'}):action('read-full-state',{reason:'Target scene is absent; inspect the current timeline count.'});
    }
    return action('open-upload',{controls:state.controls,then:'Use the observed Insert > Upload or Replace video > Upload path; reobserve before selecting a file.'});
  }
  root.LineWorldVidsUI={summarize,uploadNext,projectIdentity};
  if(typeof module!=='undefined')module.exports=root.LineWorldVidsUI;
})(globalThis);
