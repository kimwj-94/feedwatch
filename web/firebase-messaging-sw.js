/* FeedWatch background notification worker.
 * Firebase config is supplied by the signed-in page in the service-worker URL.
 * The config contains public web identifiers only; authorization remains in
 * Firebase Auth, Firestore rules, and the server-side service account.
 */

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const link = event.notification?.data?.link || './';
  event.waitUntil((async () => {
    const windows = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of windows) {
      if ('focus' in client) {
        await client.focus();
        if ('navigate' in client) await client.navigate(link);
        return;
      }
    }
    if (clients.openWindow) await clients.openWindow(link);
  })());
});

try {
  const encoded = new URL(self.location.href).searchParams.get('config');
  if (!encoded) throw new Error('Firebase config is missing');
  const config = JSON.parse(atob(encoded));

  importScripts('https://www.gstatic.com/firebasejs/12.16.0/firebase-app-compat.js');
  importScripts('https://www.gstatic.com/firebasejs/12.16.0/firebase-messaging-compat.js');
  firebase.initializeApp(config);
  firebase.messaging();
} catch (error) {
  console.error('[FeedWatch push worker]', error);
}
