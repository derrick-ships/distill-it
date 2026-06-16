# Domain: inbox-cleanup

Bulk, sender-centric operations that reduce inbox volume: unsubscribing from unwanted senders, mass-archiving low-value mail, and tracking per-sender status so the system stops re-bothering the user.

## What this domain means across repos

Cleanup is **sender-oriented**, not message-oriented. The unit of work is "this sender / newsletter," and the system keeps a persistent status record per sender (approved / unsubscribed / auto-archived). Two recurring mechanics:

1. **Unsubscribe** — parse the RFC 2369 `List-Unsubscribe` header (and RFC 8058 one-click `List-Unsubscribe-Post`), execute the unsubscribe over HTTP safely (SSRF guards, bounded redirects), and mark the sender's status.
2. **Bulk archive** — score senders by category into confidence tiers (marketing/newsletters = high, notifications/receipts = medium, everything else = low) so the user can sweep the high-confidence pile in one action.

The shared idea: classify senders once, persist the verdict, act in bulk, and never re-prompt about a sender the user already decided on.

## Features distilled here

- [[bulk-unsubscriber--from-inbox-zero]] — safe List-Unsubscribe parsing + one-click POST/GET fallback + Newsletter status tracking.
- [[bulk-archiver--from-inbox-zero]] — category-name → confidence-tier scoring of senders for one-sweep archiving.

## Related domains

- [[ai-automation]] — the rules engine can also archive/label as an action; cleanup is the manual/bulk counterpart.
- [[email-platform]] — archiving executes through the provider abstraction.
