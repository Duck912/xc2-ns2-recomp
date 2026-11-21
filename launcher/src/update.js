import { api, errText } from './util.js';

/** The launcher's update state, shared by the nav and the About page. */
export const upd = {
  check: null, // the last check_update answer
  checking: false,
  error: '',
  status: { state: 'idle' }, // update-status
  listeners: new Set(),
};

export function notify() {
  upd.listeners.forEach((fn) => fn());
}

export async function checkNow() {
  // Nothing to follow yet. The project this launcher came from has been taken down, and this fork publishes no
  // release packages, so asking GitHub would only produce "Could not reach GitHub" on the About page. The Rust
  // side (src-tauri/src/update.rs) is kept whole: when there is a release to follow, set FEFW_UPDATE_REPO and the
  // asset names there and drop this early return.
  upd.checking = false;
  upd.error = '';
  upd.check = { current: '', package: false, newer: false, latest: null };
  notify();
}

export const available = () => !!(upd.check && upd.check.package && upd.check.newer && upd.check.latest);
