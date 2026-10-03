# Security Policy & Safe Crawling Architecture — Signalpost

Signalpost operates under strict defensive engineering principles to ensure safe crawling, network containment, credential hygiene, and adherence to legal regulations.

## 1. Zero Hardcoded Secrets (Rule N6)
- **Environment Variables Only**: All credentials (e.g. `NAV_FEED_TOKEN`, `SEARCH_API_KEY`, `LLM_API_KEY`) are read exclusively from environment variables.
- **Git & Artifact Containment**: Secrets are never checked into version control. `.env` and local secrets files are excluded via `.gitignore`.
- **Payload Redaction**: Secrets, tokens, and authorization headers are never logged to console, written to JSON lines logs, or serialized into envelope artifacts.
- **Graceful Degradation**: Missing API keys never crash the pipeline or raise unhandled exceptions; missing keys degrade gracefully into deterministic fallback pathways (e.g., deterministic slug generation or open endpoints).

## 2. Server-Side Request Forgery (SSRF) Defenses
To prevent SSRF attacks against internal network infrastructure, link-local metadata services, or loopback interfaces, Signalpost validates all candidate URLs before opening network connections:
- **`assert_public_url`**: Every target hostname is resolved via DNS before connection. Private, loopback, link-local, and reserved IPv4/IPv6 ranges are strictly rejected:
  - `127.0.0.0/8` (Loopback)
  - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (Private RFC 1918)
  - `169.254.0.0/16` (Link-local / Cloud metadata service)
  - `fc00::/7`, `fe80::/10`, `::1` (IPv6 Private & Loopback)
- **Safe Redirect Handler**: All HTTP redirects (`301`, `302`, `307`, `308`) re-verify the destination URL against `assert_public_url` before following. Bounded to a maximum of 5 redirects to prevent infinite redirect loops.
- **Scheme Restriction**: Only `http://` and `https://` schemes are permitted. Schemes such as `file://`, `ftp://`, or `gopher://` are rejected immediately.

## 3. Crawling Bounds & Resource Limits
- **Page Size Cap**: Maximum response body size is hard-capped at 10 MB. Streams exceeding this cap are aborted to prevent resource exhaustion (decompression bombs).
- **Timeout Envelopes**: HTTP connection timeout is set to 5 seconds; read timeout is set to 10 seconds.
- **Fetch Bounded Scope**: The crawler visits at most 5 pages per company (homepage, about, contact, impressum/privacy).
- **Concurrency Rate Limiting**: Outbound network requests are throttled per domain with rate limiters to avoid overwhelming host servers.

## 4. Robots.txt Compliance & Crawling Etiquette
- **Robots Parser**: The crawler fetches and caches `/robots.txt` for every candidate host.
- **Honor Disallow Directives**: If a path is disallowed for our User-Agent (or `*`), Signalpost aborts retrieval and records the field state as `not_available` (`blocked_by_robots_txt`).
- **User-Agent String**: All outbound HTTP headers carry a clear, transparent User-Agent string:
  ```text
  Signalpost-Agent/1.0 (+https://builderr.ai/challenges/signalpost; research-bot)
  ```
  This identifies the agent, provides contest context, and supplies a contact URL for system administrators.
