# Encrypted eCPM immediate reward (2026-10-31)

The TAKU completion endpoint continues to require an encrypted CNY price,
key ID and matching ad source. Missing/invalid ciphertext or unavailable keys
never fall back to a client plaintext price. A successful completion credits
the wallet and coin log in one transaction without waiting for S2S delivery.

## Fixed-price source correction

Production completion requests for game 238 returned HTTP 409 after the first
reward because distinct SDK requests reused the exact same encrypted fixed
price. The decoded value was CNY eCPM 0.01 and contained no request ID.
Using the ciphertext hash as a globally single-use proof rejected subsequent
legitimate displays.

For ciphertext containing a request ID, the original decrypted-request replay
check remains. For fixed-price ciphertext without one, completion now requires:

- Nonempty SDK request ID and show ID.
- A persisted shown event matching request ID, show ID and source.
- The same encrypted CNY price hash as the shown event.
- An unused request and show identity for this game/source, including previous
  client rewards written before the correction and known callback transactions.

Unique event reservations and the existing settlement transaction prevent
duplicate credits. Distinct requests/shows may legitimately reuse the price.
No new database schema or client payload fields are required.

## Evidence boundary

SDK request/show identifiers are client-reported when absent from the encrypted
payload. Matching them provides consistency and idempotency, not a provider
signature proving a unique display. This retains the existing immediate-credit
model; S2S and later reports remain reconciliation evidence. No plaintext-price
fallback was introduced. Historical hash-only metadata cannot replace original
ciphertext for replaying an unpaid completion.

This change does not automatically backfill historical rewards or alter reward
rates. Previous client completion retries can settle only after providing the
original valid encrypted proof and matching display metadata within the existing
recovery window.
