// Decide which backend to use.
// If a valid firebase_config.json is served next to the app (apiKey + projectId),
// run in CLOUD mode (live Firestore + Auth). Otherwise run the keyless DEMO mode.
// A missing config file is the normal demo case and is handled quietly.

export async function detectMode() {
  if (window.__FEEDWATCH_CONFIG__ && window.__FEEDWATCH_CONFIG__.apiKey) {
    return { mode: 'cloud', firebaseConfig: window.__FEEDWATCH_CONFIG__ };
  }
  try {
    const res = await fetch(new URL('../firebase_config.json', import.meta.url), { cache: 'no-store' });
    if (res.ok) {
      const cfg = await res.json();
      if (cfg && cfg.apiKey && cfg.projectId) {
        if (!cfg.authDomain) cfg.authDomain = `${cfg.projectId}.firebaseapp.com`;
        return { mode: 'cloud', firebaseConfig: cfg };
      }
    }
  } catch { /* no config -> demo */ }
  return { mode: 'demo', firebaseConfig: null };
}
