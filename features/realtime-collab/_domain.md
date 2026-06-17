# Domain: realtime-collab

Multiplayer over a shared document: how concurrent edits sync, merge, and persist while staying consistent across clients — and, where it matters, private from the server. Covers WebSocket relays, presence, end-to-end encryption, deterministic per-object merge (last-write-wins with nonce tiebreak), and encrypted-at-rest persistence.

## Features in this domain

- [[e2e-encrypted-collaboration--from-excalidraw]] — zero-knowledge collab: AES-GCM room key in the URL fragment, socket.io relay that only routes ciphertext, delta broadcast + periodic full resync, reliable-vs-volatile delivery, encrypted Firebase persistence with transactional reconcile.
- [[scene-reconciliation--from-excalidraw]] — CRDT-free deterministic merge of two element lists via `version` (logical clock) + `versionNonce` (lowest-wins tiebreaker), with active-editing guards; runs both client-side and inside the save transaction.
