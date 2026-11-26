import { api, esc, icon, refreshIcons, errText, toast } from '../util.js';
import { t } from '../i18n.js';

export async function render(el, ctx) {
  let snapshot = null;
  let draftOrder = [];
  let draftDisabled = new Set();
  let draftChoices = {};
  let draftCheats = {};
  const expanded = new Set();
  let dragSource = null;

  function syncDraft(snap) {
    snapshot = snap;
    draftOrder = snap.mods.map((m) => m.folder);
    draftDisabled = new Set(snap.mods.filter((m) => !m.enabled).map((m) => m.folder));
    draftChoices = {};
    draftCheats = {};
    for (const m of snap.mods) {
      if (m.options.length) {
        draftChoices[m.folder] = {};
        for (const o of m.options) {
          draftChoices[m.folder][o.key] = o.kind === 'toggle' ? o.value === 'true' : o.value;
        }
      }
      const on = m.cheats.filter((c) => c.enabled).map((c) => c.title);
      draftCheats[m.folder] = new Set(on);
    }
    ctx.setModsRebuild?.(Boolean(snap.needs_rebuild));
  }

  function sameSet(a, b) {
    if (a.size !== b.size) return false;
    for (const x of a) if (!b.has(x)) return false;
    return true;
  }

  function dirtyCount() {
    if (!snapshot) return 0;
    let count = 0;
    const origOrder = snapshot.mods.map((m) => m.folder);
    if (origOrder.length !== draftOrder.length || origOrder.some((v, i) => v !== draftOrder[i])) count++;
    for (const m of snapshot.mods) {
      const origEnabled = m.enabled;
      const nowEnabled = !draftDisabled.has(m.folder);
      if (origEnabled !== nowEnabled) count++;
      for (const o of m.options) {
        const origVal = o.kind === 'toggle' ? o.value === 'true' : o.value;
        const curVal = draftChoices[m.folder]?.[o.key];
        if (origVal !== curVal) count++;
      }
      const origCheats = new Set(m.cheats.filter((c) => c.enabled).map((c) => c.title));
      const curCheats = draftCheats[m.folder] ?? new Set();
      if (!sameSet(origCheats, curCheats)) count++;
    }
    return count;
  }

  function hasDrawer(m) {
    return Boolean(m.meta_error || m.meta?.description || m.options.length || m.cheats.length || m.conflicts.length);
  }

  function chipHtml(cls, label) {
    return `<span class="mod-chip ${cls}">${esc(label)}</span>`;
  }

  function renderOption(m, o) {
    const val = draftChoices[m.folder]?.[o.key];
    const targetPath = o.kind === 'select'
      ? (o.choices.find((c) => c.id === val)?.path ?? o.path)
      : (val ? o.path : '');
    const hintParts = [];
    if (o.hint) hintParts.push(o.hint);
    if (targetPath) hintParts.push(`→ ${targetPath}`);
    const pathWarn = o.unsafe_path ? `<span class="mod-chip danger">${esc(t('mods.unsafePath'))}</span>` : '';

    let control = '';
    if (o.kind === 'toggle') {
      control = `<label class="switch"><input type="checkbox" data-opt-toggle="${esc(m.folder)}" data-opt-key="${esc(o.key)}" ${val ? 'checked' : ''} /><span>${esc(t(val ? 'common.on' : 'common.off'))}</span></label>`;
    } else {
      control = `<select data-opt-select="${esc(m.folder)}" data-opt-key="${esc(o.key)}">${o.choices
        .map((c) => `<option value="${esc(c.id)}" ${c.id === val ? 'selected' : ''}>${esc(c.label)}</option>`)
        .join('')}</select>`;
    }
    return `<div class="field">
      <div>
        <label class="name">${esc(o.label)} ${pathWarn}</label>
        ${hintParts.length ? `<span class="hint">${esc(hintParts.join(' · '))}</span>` : ''}
      </div>
      <div class="control">${control}</div>
    </div>`;
  }

  function renderCheats(m) {
    if (!m.cheats.length) return '';
    const byFile = new Map();
    for (const c of m.cheats) {
      if (!byFile.has(c.file)) byFile.set(c.file, []);
      byFile.get(c.file).push(c);
    }
    const enabledSet = draftCheats[m.folder] ?? new Set();
    let html = '';
    for (const [file, list] of byFile.entries()) {
      html += `<div class="mod-cheats">
        <div class="mod-subhead">${esc(t('mods.cheatsHeader', { file }))}</div>
        ${list
          .map((c) => {
            const on = enabledSet.has(c.title);
            const badge = c.kind === 'code'
              ? chipHtml('warn', t('mods.cheatKindCode'))
              : chipHtml('', t('mods.cheatKindMem'));
            return `<label class="mod-cheat-row">
              <span class="switch"><input type="checkbox" data-cheat-mod="${esc(m.folder)}" data-cheat-title="${esc(c.title)}" ${on ? 'checked' : ''} /><span>${esc(c.title)}</span></span>
              ${badge}
            </label>`;
          })
          .join('')}
      </div>`;
    }
    return html;
  }

  function renderConflicts(m) {
    if (!m.conflicts.length) return '';
    return `<div>
      <div class="mod-subhead">${esc(t('mods.conflictsHeader', { count: m.conflict_count }))}</div>
      <ul class="mod-conflicts">
        ${m.conflicts
          .map((c) => {
            const msg = c.role === 'wins'
              ? t('mods.conflictWins', { peer: c.peer })
              : t('mods.conflictLoses', { peer: c.peer });
            return `<li><code>${esc(c.path)}</code> — ${esc(msg)}</li>`;
          })
          .join('')}
      </ul>
    </div>`;
  }

  function renderModCard(m, idx, total) {
    const enabled = !draftDisabled.has(m.folder);
    const isOpen = expanded.has(m.folder);
    const drawerAvail = hasDrawer(m);
    const cardState = !enabled ? 'disabled' : m.pending_rebuild ? 'warn' : (idx === 0 ? 'accent' : '');

    const title = m.meta?.name ? m.meta.name : m.folder;
    const subParts = [];
    if (m.meta?.name && m.meta.name !== m.folder) subParts.push(m.folder);
    if (m.meta?.version) subParts.push(`v${m.meta.version}`);
    if (m.meta?.author) subParts.push(m.meta.author);

    const badges = [];
    if (m.caps.romfs) badges.push(chipHtml('ok', t('mods.capRomfs')));
    if (m.caps.archive) badges.push(chipHtml('', t('mods.capArchive')));
    if (m.caps.code_patches > 0) badges.push(chipHtml('', t('mods.capCodePatches', { count: m.caps.code_patches })));
    if (m.caps.unmatched_patches > 0) badges.push(chipHtml('danger', t('mods.capUnmatched', { count: m.caps.unmatched_patches })));
    if (m.cheats.length > 0) {
      const activeCheats = draftCheats[m.folder]?.size ?? 0;
      badges.push(chipHtml('', t('mods.capCheats', { active: activeCheats, total: m.cheats.length })));
    }
    if (m.pending_rebuild && enabled) badges.push(chipHtml('warn', t('mods.capPendingRebuild')));
    if (m.version_mismatch && m.meta?.game) badges.push(chipHtml('danger', t('mods.capWrongGame', { game: m.meta.game })));
    if (m.conflict_count > 0 && enabled) badges.push(chipHtml('warn', t('mods.capConflicts', { count: m.conflict_count })));

    let drawerHtml = '';
    if (isOpen && drawerAvail) {
      drawerHtml = `<div class="mod-drawer">
        ${m.meta_error ? `<div class="banner warn">${icon('triangle-alert')}<div>${esc(m.meta_error)}</div></div>` : ''}
        ${m.meta?.description ? `<p class="dim">${esc(m.meta.description)}</p>` : ''}
        ${m.options.map((o) => renderOption(m, o)).join('')}
        ${renderCheats(m)}
        ${renderConflicts(m)}
      </div>`;
    }

    return `<div class="mod-card ${cardState}" data-folder="${esc(m.folder)}" draggable="true">
      <div class="mod-head">
        <span class="mod-grip" title="${esc(t('mods.dragHint'))}">${icon('grip-vertical')}</span>
        <input type="checkbox" data-toggle-mod="${esc(m.folder)}" ${enabled ? 'checked' : ''} aria-label="${esc(title)}" />
        <div class="mod-title-wrap">
          <span class="mod-name">${esc(title)}</span>
          ${subParts.length ? `<span class="mod-meta">${esc(subParts.join(' · '))}</span>` : ''}
        </div>
        <span class="mod-rank">#${idx + 1}</span>
        <div class="mod-actions">
          <button class="btn icon-sm" data-move="${esc(m.folder)}" data-dir="-1" ${idx === 0 ? 'disabled' : ''} title="${esc(t('mods.moveUp'))}">${icon('chevron-up')}</button>
          <button class="btn icon-sm" data-move="${esc(m.folder)}" data-dir="1" ${idx === total - 1 ? 'disabled' : ''} title="${esc(t('mods.moveDown'))}">${icon('chevron-down')}</button>
          <button class="btn icon-sm" data-open-mod="${esc(m.folder)}" title="${esc(t('mods.openOneFolder'))}">${icon('folder-open')}</button>
          ${drawerAvail ? `<button class="btn icon-sm" data-expand="${esc(m.folder)}" title="${esc(t('mods.toggleDetails'))}">${icon(isOpen ? 'chevron-down' : 'chevron-right')}</button>` : ''}
        </div>
      </div>
      ${badges.length ? `<div class="mod-badges">${badges.join('')}</div>` : ''}
      ${drawerHtml}
    </div>`;
  }

  function draw() {
    if (!snapshot) {
      el.innerHTML = `<div class="page"><div class="hero"><h1>${esc(t('mods.title'))}</h1><p class="dim lead">${esc(t('mods.loading'))}</p></div></div>`;
      return;
    }

    const modByFolder = new Map(snapshot.mods.map((m) => [m.folder, m]));
    const orderedMods = draftOrder.map((f) => modByFolder.get(f)).filter(Boolean);
    const enabledCount = orderedMods.filter((m) => !draftDisabled.has(m.folder)).length;
    const disabledCount = orderedMods.length - enabledCount;
    const dirty = dirtyCount();

    const summary = orderedMods.length
      ? t('mods.summaryChip', { enabled: enabledCount, disabled: disabledCount })
      : t('mods.emptyChip');

    el.innerHTML = `
      <div class="page">
        <div class="hero">
          <h1>${esc(t('mods.title'))}</h1>
          <p class="dim lead">${esc(t('mods.lead'))}</p>
          <p class="faint note">${esc(t('mods.priorityNote'))}</p>
        </div>

        <div class="row between wrap">
          <span class="chip ${enabledCount ? 'ok' : ''}">${icon('package')}<span>${esc(summary)}</span></span>
          <div class="row wrap">
            <button class="btn primary" id="add-mod">${icon('plus')}${esc(t('mods.addMod'))}</button>
            <button class="btn" id="refresh-mods">${icon('refresh-cw')}${esc(t('mods.refresh'))}</button>
            <button class="btn" id="open-mods-root">${icon('folder-open')}${esc(t('play.openModsFolder'))}</button>
          </div>
        </div>

        ${snapshot.game_running ? `<div class="banner info">${icon('circle-alert')}<div>${esc(t('mods.runningBanner'))}</div></div>` : ''}
        ${snapshot.needs_rebuild ? `<div class="banner warn">
          ${icon('triangle-alert')}
          <div style="flex:1">
            <div>${esc(t('mods.rebuildBanner', { modules: snapshot.rebuild_modules.join(', ') }))}</div>
            <div style="margin-top: var(--space-2)"><button class="btn primary" id="go-rebuild">${icon('hammer')}${esc(t('mods.rebuildNow'))}</button></div>
          </div>
        </div>` : ''}

        ${orderedMods.length === 0
          ? `<div class="card">
              <p class="dim">${esc(t('mods.emptyDesc'))}</p>
              <div class="path">${esc(snapshot.mods_dir)}</div>
            </div>`
          : `<div class="mod-list">${orderedMods.map((m, i) => renderModCard(m, i, orderedMods.length)).join('')}</div>`}

        ${dirty > 0 ? `<div class="savebar">
          <span class="dim">${esc(dirty === 1 ? t('common.unsavedOne') : t('common.unsavedMany', { count: dirty }))}</span>
          <div class="row">
            <button class="btn quiet" id="discard-mods">${icon('undo-2')}${esc(t('common.revert'))}</button>
            <button class="btn primary" id="save-mods">${icon('save')}${esc(t('common.save'))}</button>
          </div>
        </div>` : ''}
      </div>`;
    refreshIcons();
    wireEvents();
  }

  function moveMod(folder, delta) {
    const i = draftOrder.indexOf(folder);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= draftOrder.length) return;
    [draftOrder[i], draftOrder[j]] = [draftOrder[j], draftOrder[i]];
    draw();
  }

  function wireEvents() {
    el.querySelector('#refresh-mods')?.addEventListener('click', load);
    el.querySelector('#open-mods-root')?.addEventListener('click', () => api('open_mods_dir').catch((e) => toast(errText(e), 'error')));
    el.querySelector('#go-rebuild')?.addEventListener('click', () => ctx.go('setup'));
    el.querySelector('#add-mod')?.addEventListener('click', async () => {
      const folder = await api('pick_folder', { title: t('mods.pickModTitle'), start: null }).catch(() => null);
      if (!folder) return;
      try {
        const snap = await api('install_mod_folder', { sourcePath: folder });
        syncDraft(snap);
        draw();
        toast(t('mods.added'), 'ok');
      } catch (e) {
        toast(errText(e), 'error');
      }
    });

    el.querySelectorAll('[data-toggle-mod]').forEach((cb) =>
      cb.addEventListener('change', () => {
        const f = cb.dataset.toggleMod;
        if (cb.checked) draftDisabled.delete(f);
        else draftDisabled.add(f);
        draw();
      }),
    );

    el.querySelectorAll('[data-move]').forEach((btn) =>
      btn.addEventListener('click', () => moveMod(btn.dataset.move, Number(btn.dataset.dir))),
    );

    el.querySelectorAll('[data-open-mod]').forEach((btn) =>
      btn.addEventListener('click', () => api('open_mod_folder', { name: btn.dataset.openMod }).catch((e) => toast(errText(e), 'error'))),
    );

    el.querySelectorAll('[data-expand]').forEach((btn) =>
      btn.addEventListener('click', () => {
        const f = btn.dataset.expand;
        if (expanded.has(f)) expanded.delete(f);
        else expanded.add(f);
        draw();
      }),
    );

    el.querySelectorAll('[data-opt-select]').forEach((sel) =>
      sel.addEventListener('change', () => {
        const f = sel.dataset.optSelect;
        if (!draftChoices[f]) draftChoices[f] = {};
        draftChoices[f][sel.dataset.optKey] = sel.value;
        draw();
      }),
    );

    el.querySelectorAll('[data-opt-toggle]').forEach((cb) =>
      cb.addEventListener('change', () => {
        const f = cb.dataset.optToggle;
        if (!draftChoices[f]) draftChoices[f] = {};
        draftChoices[f][cb.dataset.optKey] = cb.checked;
        draw();
      }),
    );

    el.querySelectorAll('[data-cheat-mod]').forEach((cb) =>
      cb.addEventListener('change', () => {
        const f = cb.dataset.cheatMod;
        const title = cb.dataset.cheatTitle;
        if (!draftCheats[f]) draftCheats[f] = new Set();
        if (cb.checked) draftCheats[f].add(title);
        else draftCheats[f].delete(title);
        draw();
      }),
    );

    el.querySelector('#discard-mods')?.addEventListener('click', () => {
      syncDraft(snapshot);
      draw();
    });

    el.querySelector('#save-mods')?.addEventListener('click', async () => {
      const cheatsEnabled = {};
      for (const [m, set] of Object.entries(draftCheats)) {
        if (set.size) cheatsEnabled[m] = Array.from(set);
      }
      try {
        const snap = await api('save_mods_state', {
          input: {
            order: draftOrder,
            disabled: Array.from(draftDisabled),
            choices: draftChoices,
            cheats_enabled: cheatsEnabled,
          },
        });
        syncDraft(snap);
        draw();
        toast(t('mods.saved'), 'ok');
      } catch (e) {
        toast(errText(e), 'error');
      }
    });

    el.querySelectorAll('.mod-card').forEach((card) => {
      card.addEventListener('dragstart', (ev) => {
        dragSource = card.dataset.folder;
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', dragSource);
      });
      card.addEventListener('dragover', (ev) => {
        if (!dragSource || dragSource === card.dataset.folder) return;
        ev.preventDefault();
        const rect = card.getBoundingClientRect();
        const before = ev.clientY < rect.top + rect.height / 2;
        card.classList.toggle('drop-before', before);
        card.classList.toggle('drop-after', !before);
      });
      card.addEventListener('dragleave', () => {
        card.classList.remove('drop-before', 'drop-after');
      });
      card.addEventListener('drop', (ev) => {
        ev.preventDefault();
        const target = card.dataset.folder;
        const before = card.classList.contains('drop-before');
        card.classList.remove('drop-before', 'drop-after');
        if (!dragSource || dragSource === target) return;
        const from = draftOrder.indexOf(dragSource);
        if (from < 0) return;
        draftOrder.splice(from, 1);
        let to = draftOrder.indexOf(target);
        if (!before) to++;
        draftOrder.splice(to, 0, dragSource);
        dragSource = null;
        draw();
      });
      card.addEventListener('dragend', () => {
        dragSource = null;
        el.querySelectorAll('.mod-card').forEach((c) => c.classList.remove('drop-before', 'drop-after'));
      });
    });
  }

  async function load() {
    try {
      const snap = await api('list_mods');
      syncDraft(snap);
      draw();
    } catch (e) {
      el.innerHTML = `<div class="page"><div class="banner danger">${icon('circle-x')}<div>${esc(errText(e))}</div></div></div>`;
      refreshIcons();
    }
  }

  ctx.onStatus?.((s) => {
    if (snapshot) {
      snapshot.game_running = s.state === 'running';
      draw();
    }
  });

  draw();
  await load();
}
