# End-to-End Encrypted Collaboration (build spec) — distilled from excalidraw

## Summary

Zero-knowledge real-time collaboration on commodity infra. Generate a random room ID + a 128-bit AES-GCM room key client-side; put the key in the **URL fragment** (`#room=ID,KEY`) so it never reaches the server. Encrypt every payload (scene init/update, cursor, idle) with AES-GCM + a fresh 12-byte random IV before sending over a socket.io relay that only fan-outs sealed blobs. Persist the still-encrypted scene to Firebase as `{ sceneVersion, iv, ciphertext }`, debounced + version-cached, and save inside a transaction that decrypts-merges-(reconciles)-re-encrypts so concurrent saves can't clobber. Two delivery tiers: reliable for edits, volatile for presence.

## Core logic (inlined)

**1. Crypto primitives (Web Crypto, AES-GCM 128):**
```ts
const ENCRYPTION_KEY_BITS = 128;
const IV_LENGTH_BYTES = 12;                         // GCM standard nonce length

// Generate a room key. Returned AS the JWK `k` string (base64url) so it fits in a URL.
export const generateEncryptionKey = async (): Promise<string> => {
  const key = await window.crypto.subtle.generateKey(
    { name: "AES-GCM", length: ENCRYPTION_KEY_BITS },
    true,                                            // extractable (so we can export to JWK)
    ["encrypt", "decrypt"],
  );
  const jwk = await window.crypto.subtle.exportKey("jwk", key);
  return jwk.k!;                                     // <-- this short string IS the room key
};

// Re-import that string into a CryptoKey when joining a room.
const getCryptoKey = (key: string, usage: KeyUsage) =>
  window.crypto.subtle.importKey(
    "jwk",
    { alg: "A128GCM", ext: true, k: key, key_ops: ["encrypt", "decrypt"], kty: "oct" },
    { name: "AES-GCM", length: ENCRYPTION_KEY_BITS },
    false,
    [usage],
  );

const createIV = () => {
  const arr = new Uint8Array(IV_LENGTH_BYTES);
  return window.crypto.getRandomValues(arr);         // fresh random IV PER message
};

export const encryptData = async (
  key: string | CryptoKey,
  data: Uint8Array | ArrayBuffer | Blob | File | string,
): Promise<{ encryptedBuffer: ArrayBuffer; iv: Uint8Array }> => {
  const importedKey = typeof key === "string" ? await getCryptoKey(key, "encrypt") : key;
  const iv = createIV();
  const buffer = typeof data === "string"
    ? new TextEncoder().encode(data)
    : data;                                          // (Blob/File → arrayBuffer() first)
  const encryptedBuffer = await window.crypto.subtle.encrypt(
    { name: "AES-GCM", iv }, importedKey, buffer as ArrayBuffer,
  );
  return { encryptedBuffer, iv };
};

export const decryptData = async (
  iv: Uint8Array,
  encrypted: Uint8Array | ArrayBuffer,
  privateKey: string,
): Promise<ArrayBuffer> => {
  const key = await getCryptoKey(privateKey, "decrypt");
  return window.crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, encrypted);
};
```

**2. Room id + shareable link (key lives in the FRAGMENT):**
```ts
const generateRoomId = async () => {
  const buffer = new Uint8Array(10);
  window.crypto.getRandomValues(buffer);
  return Array.from(buffer, b => b.toString(16).padStart(2, "0")).join(""); // hex
};

// THE security-critical line: key after '#', never sent to the server.
const getCollaborationLink = (data: { roomId: string; roomKey: string }) =>
  `${window.location.origin}${window.location.pathname}#room=${data.roomId},${data.roomKey}`;

// On load, read it back:
const getCollabRoomFromHash = () => {
  const m = window.location.hash.match(/^#room=([0-9a-f]+),([a-zA-Z0-9_-]+)$/);
  return m ? { roomId: m[1], roomKey: m[2] } : null;
};
```

**3. The relay client (Portal over socket.io):**
```ts
class Portal {
  socket: Socket | null = null;
  roomId: string | null = null;
  roomKey: string | null = null;                 // the JWK `k` string
  broadcastedElementVersions = new Map<string, number>(); // id -> last broadcast version

  open(socket, id, key) {
    this.socket = socket; this.roomId = id; this.roomKey = key;
    socket.on("init-room", () => socket.emit("join-room", this.roomId));
    socket.on("new-user", () => this.broadcastScene(WS_SUBTYPES.INIT, /*syncAll*/ true));
    socket.on("room-user-change", (ids) => { /* update collaborator list */ });
    socket.on("client-broadcast", (encryptedData, iv) =>
      this.handleIncoming(new Uint8Array(iv), encryptedData));
  }

  // Encrypt + emit. volatile = best-effort (presence); non-volatile = reliable (edits).
  private async _broadcastSocketData(data: SocketUpdateData, volatile = false, roomId?: string) {
    const json = JSON.stringify(data);
    const encoded = new TextEncoder().encode(json);
    const { encryptedBuffer, iv } = await encryptData(this.roomKey!, encoded);
    this.socket?.emit(
      volatile ? WS_EVENTS.SERVER_VOLATILE : WS_EVENTS.SERVER,
      roomId ?? this.roomId,
      encryptedBuffer,
      iv,
    );
  }

  broadcastScene(updateType /* INIT | UPDATE */, syncAll: boolean) {
    // INIT (new user joined) → send ALL elements. UPDATE → send only changed ones.
    const elements = getSyncableElements(this.getSceneElementsIncludingDeleted());
    const toSend = syncAll
      ? elements
      : elements.filter(e => (this.broadcastedElementVersions.get(e.id) ?? -1) < e.version);
    if (!syncAll && toSend.length === 0) return;
    const data: SocketUpdateData = { type: updateType, payload: { elements: toSend } };
    for (const e of toSend) this.broadcastedElementVersions.set(e.id, e.version);
    this._broadcastSocketData(data); // reliable
  }

  broadcastMouseLocation(payload) {
    this._broadcastSocketData(
      { type: WS_SUBTYPES.MOUSE_LOCATION, payload }, /*volatile*/ true);
  }
  broadcastIdleChange(userState) {
    this._broadcastSocketData(
      { type: WS_SUBTYPES.IDLE_STATUS, payload: { userState } }, /*volatile*/ true);
  }
}

const WS_SUBTYPES = {
  INVALID_RESPONSE: "INVALID_RESPONSE",
  INIT: "SCENE_INIT",
  UPDATE: "SCENE_UPDATE",
  MOUSE_LOCATION: "MOUSE_LOCATION",
  IDLE_STATUS: "IDLE_STATUS",
} as const;
const WS_EVENTS = { SERVER: "server-broadcast", SERVER_VOLATILE: "server-volatile-broadcast" };
```

**4. Receiving + decrypting:**
```ts
const decryptPayload = async (iv: Uint8Array, encrypted: ArrayBuffer, key: string) => {
  try {
    const decrypted = await decryptData(iv, encrypted, key);
    const json = new TextDecoder("utf-8").decode(new Uint8Array(decrypted));
    return JSON.parse(json) as SocketUpdateData;
  } catch {
    return { type: WS_SUBTYPES.INVALID_RESPONSE }; // tamper/garbage → don't crash
  }
};

// On a SCENE_INIT/SCENE_UPDATE, hand the elements to reconciliation (see scene-reconciliation doc):
async function handleIncoming(iv, encrypted) {
  const data = await decryptPayload(iv, encrypted, this.roomKey!);
  if (data.type === WS_SUBTYPES.INIT || data.type === WS_SUBTYPES.UPDATE) {
    this.collab.handleRemoteSceneUpdate(data.payload.elements); // → reconcileElements → updateScene
  }
}
```

**5. Persistence (Firebase Firestore) — encrypted blob, transactional reconcile:**
```ts
type FirebaseStoredScene = { sceneVersion: number; iv: Bytes; ciphertext: Bytes };

const SYNC_FULL_SCENE_INTERVAL_MS = 20_000;

const saveToFirebase = async (portal, elements, appState) => {
  // skip redundant writes: version cache
  if (isSavedToFirebase(portal, elements)) return null;     // sceneVersion unchanged
  const { roomId, roomKey } = portal;
  const docRef = doc(firestore, "scenes", roomId);
  const stored = await runTransaction(firestore, async (tx) => {
    const snap = await tx.get(docRef);
    let reconciled = elements;
    if (snap.exists()) {
      const prev = snap.data() as FirebaseStoredScene;
      const decrypted = await decryptData(new Uint8Array(prev.iv.toUint8Array()),
                                          prev.ciphertext.toUint8Array(), roomKey);
      const prevElements = JSON.parse(new TextDecoder().decode(decrypted));
      reconciled = reconcileElements(elements, prevElements, appState); // ← merge, don't clobber
    }
    const json = JSON.stringify(reconciled);
    const { encryptedBuffer, iv } = await encryptData(roomKey, json);
    tx.set(docRef, {
      sceneVersion: getSceneVersion(reconciled),
      ciphertext: Bytes.fromUint8Array(new Uint8Array(encryptedBuffer)),
      iv: Bytes.fromUint8Array(iv),
    });
    return reconciled;
  });
  FirebaseSceneVersionCache.set(portal.socket, stored);     // update version cache
  return stored;
};

const loadFromFirebase = async (roomId, roomKey) => {
  const snap = await getDoc(doc(firestore, "scenes", roomId));
  if (!snap.exists()) return null;
  const { iv, ciphertext } = snap.data() as FirebaseStoredScene;
  const decrypted = await decryptData(new Uint8Array(iv.toUint8Array()),
                                      ciphertext.toUint8Array(), roomKey);
  return JSON.parse(new TextDecoder().decode(decrypted)); // elements
};
```
Files/images: upload to Firebase **Storage** (also AES-GCM encrypted), with `cacheControl: public, max-age=<long>` since content is immutable; fetch by URL, decrypt, decode.

## Data contracts

```ts
// On the wire (socket.io emits): (event, roomId, encryptedBuffer: ArrayBuffer, iv: Uint8Array)
type SocketUpdateData =
  | { type: "SCENE_INIT" | "SCENE_UPDATE"; payload: { elements: ExcalidrawElement[] } }
  | { type: "MOUSE_LOCATION"; payload: { socketId; pointer; button; selectedElementIds; username } }
  | { type: "IDLE_STATUS";   payload: { userState: "active" | "idle" | "away" } };

// At rest (Firestore doc "scenes/{roomId}"):
type FirebaseStoredScene = { sceneVersion: number; iv: Bytes; ciphertext: Bytes };

// Room handle:
type RoomLink = `#room=${string /*hex roomId*/},${string /*JWK k roomKey*/}`;
```

## Dependencies & assumptions

- **Web Crypto API** (`window.crypto.subtle`, `getRandomValues`) — requires a **secure context (HTTPS/localhost)**; unavailable on plain HTTP.
- **socket.io** client + a relay server that only routes (does NOT decrypt). Relay needs: rooms, `join-room`, fan-out `server-broadcast`/`server-volatile-broadcast`, `room-user-change`.
- **Firebase** Firestore (scene blob) + Storage (files), or any equivalent KV store + object store. Transactions required for safe concurrent save.
- The reconciliation function (see [[scene-reconciliation--from-excalidraw]]) — needed both client-side and in the save transaction.
- Assumes elements carry `version`/`versionNonce` (for delta broadcast + merge).

## To port this, you need:

- [ ] AES-GCM 128 via Web Crypto: `generateEncryptionKey` (export as JWK `k`), `encryptData` (random 12-byte IV each time), `decryptData`. Served over HTTPS.
- [ ] Room key placed in the **URL fragment** (`#...`), never a query/path param. Parse it back on load.
- [ ] A relay (socket.io) that fan-outs encrypted blobs without decrypting; events for join, new-user, user-change, broadcast.
- [ ] Reliable vs volatile emit paths (edits vs presence).
- [ ] Delta broadcast via a `Map<id, lastBroadcastVersion>`, plus a periodic full re-sync (~20s).
- [ ] `decryptPayload` that returns an INVALID sentinel on failure (never throws to the UI).
- [ ] Encrypted-at-rest persistence `{ sceneVersion, iv, ciphertext }`, debounced, version-cached, saved in a transaction that decrypts→reconciles→re-encrypts.
- [ ] Reconciliation wired into both the receive path and the save transaction.

## Gotchas

- **Key MUST be in the fragment, not a query param.** `?key=` or `/key/` is sent to the server and destroys the zero-knowledge property. Only the `#fragment` is withheld from HTTP requests. This is the single most important detail.
- **Never reuse an IV with the same key.** GCM IV reuse can leak the key and break authentication. Generate a fresh `getRandomValues(12)` per `encryptData`. The IV is not secret — ship it alongside the ciphertext.
- **Use AES-GCM (authenticated), not AES-CBC.** GCM rejects tampered ciphertext; with an untrusted relay, integrity matters as much as secrecy. A failed decrypt must be handled (return INVALID), not crash.
- **Web Crypto needs a secure context.** It silently doesn't exist on `http://` (non-localhost). Deploy over TLS.
- **Save must reconcile, not overwrite.** Two near-simultaneous saves: if you just `set()` the client's elements you clobber the other's edits. Decrypt-merge-encrypt inside a transaction.
- **Version cache to avoid write storms.** Without `isSavedToFirebase`/sceneVersion check + debounce, you hammer the DB on every keystroke-equivalent.
- **Delta broadcast needs a full-resync safety net.** Pure deltas drift if a message is lost; periodically broadcast the whole scene.
- **Presence as volatile**, or cursor spam queues behind reliable edits and adds latency to everything.
- **The room key never leaves the clients** — so there's no password reset / no server-side recovery. Lose the link, lose the board. That's inherent to zero-knowledge; communicate it.

## Origin (reference only)

Repo: https://github.com/excalidraw/excalidraw  
Key files: `packages/excalidraw/data/encryption.ts` (`generateEncryptionKey`, `encryptData`, `decryptData`, `IV_LENGTH_BYTES=12`), `excalidraw-app/data/index.ts` (`generateRoomId`, `getCollaborationLink`, `decryptPayload`, `compressData`), `excalidraw-app/collab/Portal.tsx` (relay client, broadcast methods, volatile/reliable), `excalidraw-app/collab/Collab.tsx` (orchestration, `handleRemoteSceneUpdate`, `broadcastedElementVersions`), `excalidraw-app/data/firebase.ts` (`saveToFirebase` transactional reconcile, `loadFromFirebase`, `FirebaseStoredScene`).
