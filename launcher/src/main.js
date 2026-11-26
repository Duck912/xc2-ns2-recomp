import './theme.css';
import './layout.css';
import './components.css';
import './shell.css';
import { listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { api, esc, icon, refreshIcons, errText, toast } from './util.js';
import { t, initLang, getLang } from './i18n.js';
import * as home from './pages/home.js';
import * as mods from './pages/mods.js';
import * as settings from './pages/settings.js';
import * as about from './pages/about.js';
import * as files from './pages/files.js';
import { checkNow } from './update.js';

/*
 * The shell: a frameless window (tauri.conf.json decorations: false) with its own title bar, the home flow
 * (pages/home.js: home, Game files, Options, Build) and, behind the gear, the full Settings, Mods, Clean up and About pages;
 * the save-disk button beside the gear opens the Saves page (pages/files.js).
 */
const PANEL = {
  settings: { mod: settings, key: 'nav.settings' },
  mods: { mod: mods, key: 'nav.mods' },
  clean: { mod: { render: files.renderClean }, key: 'nav.clean' },
  about: { mod: about, key: 'nav.about' },
};

const view = document.getElementById('view');
let current = 'home';
let statusHandler = null;
let setupHandler = null;
let logHandler = null;

const ctx = {
  go,
  onStatus(fn) { statusHandler = fn; },
  onSetup(fn) { setupHandler = fn; },
  onLog(fn) { logHandler = fn; },
  setModsRebuild() {},
  shell() { drawShell(); },
  redraw() { drawShell(); go(current); },
};

function drawShell() {
  document.title = t('window.title');
  document.getElementById('tb-name').textContent = t('brand.name');
  document.getElementById('tb-settings').title = t('nav.settings');
  document.getElementById('tb-saves').title = t('nav.saves');
  document.getElementById('tb-min').title = t('shell.minimize');
  document.getElementById('tb-close').title = t('shell.close');
}

/** The gear's panel: a Back button and the three full pages as tabs. */
async function renderPanel(page) {
  document.getElementById('tb-center').innerHTML = '';
  view.innerHTML = `<div class="panel-tabs">
      <button class="btn quiet" id="panel-back">${icon('arrow-left')}${esc(t('shell.back'))}</button>
      ${Object.entries(PANEL).map(([id, p]) => `<button class="btn quiet ${id === page ? 'active' : ''}" data-tab="${id}">${esc(t(p.key))}</button>`).join('')}
    </div><div id="panel-body"></div>`;
  view.querySelector('#panel-back').addEventListener('click', () => go('home'));
  view.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => go(b.dataset.tab)));
  await PANEL[page].mod.render(view.querySelector('#panel-body'), ctx);
}

/** The title bar's Saves page: a Back button and the page. */
async function renderSaves() {
  document.getElementById('tb-center').innerHTML = '';
  view.innerHTML = `<div class="panel-tabs">
      <button class="btn quiet" id="panel-back">${icon('arrow-left')}${esc(t('shell.back'))}</button>
    </div><div id="panel-body"></div>`;
  view.querySelector('#panel-back').addEventListener('click', () => go('home'));
  await files.renderSaves(view.querySelector('#panel-body'));
}

async function go(page, opts = {}) {
  // The old pages' targets: "setup" is the build flow, "play" the home screen.
  if (page === 'setup') { home.start('files'); page = 'home'; }
  if (page === 'play') page = 'home';
  current = page;
  statusHandler = null;
  setupHandler = null;
  logHandler = null;
  view.scrollTop = 0;
  try {
    if (page === 'saves') await renderSaves();
    else if (PANEL[page]) await renderPanel(page);
    else await home.render(view, { ...ctx, ...opts });
  } catch (e) {
    view.innerHTML = `<div class="page"><div class="banner danger">${icon('circle-x')}<div>${esc(errText(e))}</div></div></div>`;
    toast(errText(e), 'error');
  }
  refreshIcons();
}

async function boot() {
  const win = getCurrentWindow();
  document.getElementById('tb-min').addEventListener('click', () => win.minimize());
  document.getElementById('tb-close').addEventListener('click', () => win.close());
  document.getElementById('tb-settings').addEventListener('click', () => go(PANEL[current] ? 'home' : 'settings'));
  document.getElementById('tb-saves').addEventListener('click', () => go(current === 'saves' ? 'home' : 'saves'));
  await listen('game-status', (ev) => statusHandler && statusHandler(ev.payload));
  await listen('setup-status', (ev) => setupHandler && setupHandler(ev.payload));
  await listen('setup-log', (ev) => logHandler && logHandler(ev.payload));
  let cfg = {};
  try { cfg = await api('get_config'); } catch (e) { toast(errText(e), 'error'); }
  await initLang(() => { drawShell(); go(current); }, cfg.lang);
  document.documentElement.lang = getLang();
  drawShell();
  refreshIcons();
  // XC2_LAUNCHER_PAGE (screenshots, docs): open on files | saves | clean | settings | mods | about instead of home
  const start = await api('start_page').catch(() => '');
  go(start === 'files' ? 'setup' : ['saves', ...Object.keys(PANEL)].includes(start) ? start : 'home');
  if (!cfg.skip_update_check && !start) checkNow();   // quietly: the About page shows the result
}

boot();
