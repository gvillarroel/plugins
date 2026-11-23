/* Recommend one edit in the current native editor. This module has no I/O. */
(function (root) {
  const ui = typeof module !== 'undefined' ? require('./vids-ui.js') : root.LineWorldVidsUI;
  const phases = new Set(['ready', 'await-save', 'reopened']);
  const scope = new Set(['native-ui', 'local-fixture']);
  const wait = reason => ({kind: 'observe', reason});
  const conflict = reason => ({kind: 'conflict', reason});
  const normalizeScript = value => value.replace(/\s+/g, ' ').trim();
  const validSceneId = value => typeof value === 'string' && /^id\.[a-zA-Z0-9_.-]+$/.test(value);
  const sceneOrder = state => state.scriptState?.order ?? state.selectedOrder;

  function selectScene(state, order) {
    const target = state.scenes.find(scene => scene.order === order);
    return {kind: 'select-scene', index: target.index, sceneOrder: order};
  }

  function verify(state, input, evidence) {
    if (!state.saved) return wait('Wait for the native Saved to Drive indicator.');
    if (input.phase !== 'reopened') return {kind: 'reload-to-verify'};
    return {
      kind: 'verified',
      receipt: {
        scope: input.scope,
        operation: input.plan.operation,
        status: 'reopened-and-matched',
        projectId: state.projectId,
        title: state.title,
        sceneCount: state.sceneCount,
        saveIndicator: 'Saved to Drive',
        ...evidence,
      },
    };
  }

  function changeValue(state, input, current, before, after, action, evidence) {
    if (current === after) return verify(state, input, evidence);
    if (current !== before) return conflict('The current value differs from both the baseline and requested value.');
    if (input.phase === 'reopened') return conflict('The requested value was absent after reopening the saved project.');
    if (input.phase === 'await-save') return wait('The attempted mutation is not visible yet. Inspect the editor before retrying.');
    if (!state.saved || !action) return wait('Observe a saved baseline and its enabled edit control.');
    return action;
  }

  function renameProject(state, input) {
    const {before, title} = input.plan;
    if (typeof before !== 'string' || !before.trim() || typeof title !== 'string' || !title.trim()) {
      return conflict('Supply the observed title and desired title.');
    }
    if (state.title === null) return wait('Observe the Rename field in the intended editor.');
    const index = state.controls.Rename;
    return changeValue(state, input, state.title, before, title,
      index === undefined ? null : {kind: 'rename-project', index, title}, {});
  }

  function setScript(state, input) {
    const {before, script, sceneId, order, count} = input.plan;
    if (typeof before !== 'string' || typeof script !== 'string' || !script.trim() ||
        (before !== script && normalizeScript(before) === normalizeScript(script)) ||
        !validSceneId(sceneId) || !Number.isInteger(order) || order < 1 ||
        !Number.isInteger(count) || order > count) {
      return conflict('Supply an observable text change, a scene ID, its position, and the observed timeline size.');
    }
    if (state.sceneCount !== count) return conflict('The timeline size changed. Reinspect scene identities.');
    if (state.sceneId !== sceneId || sceneOrder(state) !== order) {
      if (sceneOrder(state) === order && state.sceneId !== sceneId) {
        return conflict('The scene in this position has a different native ID.');
      }
      return selectScene(state, order);
    }
    const panel = state.scriptState;
    if (!panel || panel.order !== order || panel.count !== count) {
      const current = state.tabs['Current scene'];
      if (current !== undefined && panel?.order === null) return {kind: 'show-current-scene', index: current};
      if (panel || current !== undefined || state.voiceoverOpen) return wait('Confirm the Current scene panel for this scene before editing.');
      const voiceover = state.controls.Voiceover;
      return voiceover === undefined ? wait('Observe the Voiceover control.') : {kind: 'open-voiceover', index: voiceover};
    }
    const index = state.controls['Edit script'];
    return changeValue(state, input, normalizeScript(panel.text), normalizeScript(before), normalizeScript(script),
      index === undefined ? null : {kind: 'edit-script', index, sceneId, script},
      {sceneId, sceneOrder: order, observedScript: panel.text, scriptMatch: 'normalized-visible-text'});
  }

  function appendScene(state, input) {
    const {count, anchorSceneId, createdSceneId} = input.plan;
    if (!Number.isInteger(count) || count < 1 || !validSceneId(anchorSceneId) ||
        (createdSceneId !== undefined && (!validSceneId(createdSceneId) || createdSceneId === anchorSceneId))) {
      return conflict('Supply the original timeline size and last scene ID. Record any new ID after observing the append.');
    }
    if (state.sceneCount === count + 1) {
      if (!createdSceneId && input.phase !== 'await-save') {
        return conflict('An extra scene exists without a recorded append. Identify it before doing any other write.');
      }
      if (sceneOrder(state) !== count + 1) return selectScene(state, count + 1);
      if (createdSceneId) {
        if (state.sceneId !== createdSceneId) return conflict('The last scene has a different native ID.');
        return verify(state, input, {anchorSceneId, createdSceneId, sceneOrder: count + 1});
      }
      if (!validSceneId(state.sceneId) || state.sceneId === anchorSceneId) {
        return wait('Observe the new native scene ID in the editor URL.');
      }
      return {
        kind: 'record-appended-scene',
        createdSceneId: state.sceneId,
        sceneOrder: count + 1,
        reason: 'Record this ID only after confirming your one append and its new blank scene in the editor.',
      };
    }
    if (state.sceneCount !== count || createdSceneId || input.phase === 'reopened') {
      return conflict('The timeline does not match the recorded append state.');
    }
    if (input.phase === 'await-save') return wait('One append is pending. Inspect the editor before any retry.');
    if (sceneOrder(state) !== count) return selectScene(state, count);
    if (state.sceneId !== anchorSceneId) return conflict('The last scene has a different native ID.');
    const index = state.controls['New scene (Ctrl+M)'] ?? state.controls['New scene'];
    if (index === undefined || !state.saved) return wait('Observe a saved baseline and the enabled New scene control.');
    return {kind: 'append-scene', index, afterSceneId: anchorSceneId};
  }

  const operations = new Map([
    ['rename-project', renameProject],
    ['set-script', setScript],
    ['append-scene', appendScene],
  ]);

  function editNext(input) {
    if (input.policyStopped) return {kind: 'stop', reason: 'Follow the host handoff.'};
    if (input.fullState !== true) return {kind: 'read-full-state'};
    if (input.foreground !== true) return {kind: 'foreground-editor'};
    const state = ui.summarize(input.ax);
    const expected = ui.projectIdentity(input.plan?.projectUrl);
    if (!state.recognized || !expected || state.projectId !== expected.id) {
      return {kind: 'verify-project', reason: 'Observe the exact intended Vids editor before any edit.'};
    }
    const operation = operations.get(input.plan.operation);
    if (!operation || !phases.has(input.phase) || !scope.has(input.scope)) {
      return conflict('Supply a supported operation, verification phase and observation scope.');
    }
    if (!state.sceneCount) return {kind: 'read-full-state', reason: 'Observe the complete scene timeline.'};
    return operation(state, input);
  }

  root.LineWorldVidsEdit = {editNext};
  if (typeof module !== 'undefined') module.exports = root.LineWorldVidsEdit;
})(globalThis);
