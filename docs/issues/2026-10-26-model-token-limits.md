# Model limits in Research settings

Scope: discover advertised limits for configured API models and allow an optional
maximum output-token override. No inference or research run is needed for discovery.

## Implementation

- GET `/api/model-limits` validates the current saved or supplied draft model
  settings, then reads the configured endpoint's `/models` response.
- Distinguish loaded context, advertised output maximum and default output.
  Unavailable metadata stays unknown. Training context is not a loaded limit.
- Retry transient network failures and HTTP 408/429/500/502/503/504 three times
  after the initial attempt, with timeouts 10, 20, 30 and 30 seconds.
- Settings automatically checks each selected provider/endpoint/model combination
  and offers Refresh model limits. Old responses cannot overwrite a changed draft.
- A positive integer `max_tokens` is saved through normal revision checks; blank
  means no request override. Existing factory forwarding applies to both research
  and portfolio synthesis. Codex manages its own limits; the field is disabled.
- Discovery does not hold the service maintenance lock during server requests.
- Convert the existing token-limit environment value to an integer before strict
  desk configuration validation.

## Delivery evidence

Source: working changes over `580f1c8`, branch `nautilus`.
Windows desktop package 0.6.1 installed successfully; the installed executable
reports version 0.6.1. Its installer and updater signature were produced from
the completed batch. NSIS now uses zlib for subsequent packaging.

One affected Settings visit confirmed both models discover the current server's
210,000-token loaded context and 65,536-token default output budget. The server's
loaded context changed from the earlier 239,872-token observation; the UI showed
the new value. No separate output maximum was advertised, so it remains Unknown.

Saved a 65,536-token override through the UI and confirmed the stored value using
the API. Cleared and saved it again to restore the user's server-default setting.
The account remained verified. Screenshot: `model-token-limits-20261026.png` in
the session visualization directory. Retry failure paths were source-reviewed;
no outage was manufactured. No automated tests or research reruns were performed.
