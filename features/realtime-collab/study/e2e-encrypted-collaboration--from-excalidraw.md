# End-to-End Encrypted Collaboration — from [excalidraw](https://github.com/excalidraw/excalidraw)

> Domain: [[_domain]] · Source: https://github.com/excalidraw/excalidraw · NotebookLM: 

## What it does

When you click "Share" in Excalidraw, you get a link like `excalidraw.com/#room=a1b2c3,XYZ...`. Anyone with that link joins a live session where everyone's cursors, selections, and edits sync in real time. The remarkable part: **Excalidraw's own servers can't read your drawing.** The board is encrypted on your device before it ever leaves, and the only key that can decrypt it lives in the part of the URL *after the `#`* — which browsers never send to the server. So the relay server and the storage database see nothing but ciphertext. It's a genuinely zero-knowledge collaboration system that runs on commodity infrastructure (a small WebSocket relay + Firebase).

## Why it exists

Two motivations. First, **trust as a product feature**: teams sketch sensitive things — unreleased products, org charts, architecture, client work. "We literally cannot see your boards" is a far stronger promise than "we promise not to look," and it's a real differentiator for an open-source tool competing with corporate SaaS. Second, **cost and simplicity**: because the server is just a dumb relay passing encrypted blobs, Excalidraw doesn't need to run expensive trusted backend logic, and the free hosted service stays cheap to operate. Encryption isn't bolted on; it's what lets the architecture be so lean.

## How it actually works

**The room and its key.** When you start a session, the client generates two random things locally: a **room ID** (random hex, the public address of the session) and a **room key** (a 128-bit AES key). The link encodes both — but crucially the key goes in the URL **fragment** (`#room=ID,KEY`). The fragment is a browser quirk that's pure gold here: it's part of the URL but is *never transmitted to the server* on any request. So when you share the link, the key reaches your collaborators' browsers but never touches Excalidraw's servers. The server knows the room exists and routes its traffic; it has no way to decrypt the contents.

**Encrypting before sending.** Every payload — a scene update, a batch of elements, even a cursor position — is serialized, then encrypted with AES-GCM using the room key and a fresh random initialization vector (IV). AES-GCM is "authenticated" encryption, meaning it also detects tampering: a corrupted or forged message fails to decrypt rather than silently producing garbage. The encrypted bytes plus the IV are what travel over the wire. On the other end, collaborators decrypt with the same room key and an attacker without the key sees only noise.

**The relay (Portal).** A WebSocket server (via socket.io) is the postal service. Clients open a connection, join their room, and the server fan-outs each encrypted message to the other members. The server never decrypts — it's moving sealed envelopes. There are a few message types:
- **Scene init** — when a new collaborator joins, an existing client sends them the *entire* current board so they start in sync.
- **Scene update** — incremental edits. To save bandwidth, a client only sends the elements whose version changed since it last broadcast them, tracked in a small "what version did I last send for each element" table. Periodically it re-sends the whole scene anyway, as a safety net against drift.
- **Cursor/selection and idle status** — presence info, sent as "volatile" messages: if one gets dropped by the network, who cares, the next one is milliseconds away.

That **volatile vs. reliable** split is a nice touch: edits use guaranteed delivery, but cursor positions use best-effort delivery so they don't clog the pipe or get queued during congestion.

**Persistence.** A live relay is ephemeral — if everyone closes the tab, the session is gone. So Excalidraw also saves the (still encrypted) scene to Firebase. The stored record is just `{ sceneVersion, iv, ciphertext }` — the database holds an opaque encrypted blob and a version number. Saves are debounced and skipped entirely if nothing changed since the last save (a version cache avoids redundant writes). And because two people might save near-simultaneously, the save runs inside a transaction that *decrypts the previously stored scene, merges it with the incoming one (reconciliation), re-encrypts, and writes* — so a save can never silently overwrite a collaborator's work. Images and other binary files go to Firebase Storage, also encrypted, with long cache headers since their content never changes.

**Joining a room.** Open the link → browser reads `#room=ID,KEY` → client connects to the relay with the ID, asks for the current scene, and pulls the stored scene from Firebase, decrypting both with the KEY from the fragment. From there it's live.

## The non-obvious parts

- **The URL fragment is the entire security model.** Putting the key after `#` (not in a query param, not in the path) is what makes it zero-knowledge — fragments are never sent in HTTP requests. Get this detail wrong (e.g. `?key=`) and the server suddenly sees every key.
- **AES-GCM, not just AES.** GCM adds authentication, so tampered messages are *rejected*, not decrypted into garbage. For a relay you don't fully trust, that integrity check matters as much as the secrecy.
- **A fresh random IV per message.** Reusing an IV with the same key is catastrophic for GCM (it can leak the key). Excalidraw generates 12 random bytes per encryption and ships the IV alongside the ciphertext (the IV isn't secret).
- **Delta broadcasting with a version table.** Only changed elements are sent, but a periodic full re-sync guards against missed updates. It's an optimization with a built-in safety valve.
- **Volatile presence vs. reliable edits.** Cursors are allowed to drop; edits are not. Two delivery tiers over the same socket.
- **The server is deliberately dumb.** It can't reconcile, can't validate, can't read. All intelligence is on the clients. That's what keeps the backend cheap and the privacy guarantee honest.
- **Saving reconciles, not overwrites.** The transactional decrypt-merge-encrypt on persist is what makes concurrent saves safe even though the storage layer is "just" a key-value blob store.

## Related

- [[scene-reconciliation--from-excalidraw]] (the merge run both on each client and inside the Firebase save transaction)
- [[fractional-indexing--from-excalidraw]] (z-order that must survive the round-trip and concurrent edits)
- See also: any "key-in-the-fragment" zero-knowledge sharing pattern (PrivateBin, Firefox Send-style tools) uses the same fragment trick.
