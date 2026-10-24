# TAKU encrypted eCPM verification

Protocol: https://help.takuad.com/docs/ecpm_key

## Global admin settings

Superadmins can open Advertising Settings (`#ad-settings`) and fill the global
Publisher Key and server/client eCPM RSA PEM private keys, each with its TAKU
Key ID (`s_id`). The API is GET/PATCH `/api/v1/settings/taku-keys`.
GET and PATCH responses contain configured flags and key IDs only. Blank inputs
preserve stored values; saving clears the browser's secret fields. New eCPM IDs
retain previous keys for in-flight callbacks; an existing ID cannot be replaced
with a different key. Both client and server eCPM private keys stay on the server.

The global Publisher Key supplies the callback signing secret only for games
without an explicit game callback configuration. Existing game secrets and
explicit disabled/cleared settings retain priority. A configured game keyring file
takes priority over global database eCPM keys. Apply migration `e934_taku_global_keys`
before starting the new code. Protect database backups as they contain credentials.
As of 2026-10-13, the supplied Publisher Key and both eCPM RSA private keys,
with their supplied TAKU Key IDs, are saved in the deployed global settings.
Authenticated API readback confirmed all three configured flags and both IDs.
Aliyun AccessKeys and the Android risk AppKey are not substitutes.

The failed callback examined on 2026-10-13 contains literal `{s_id}`, `{e_c}`,
and `{e_c_cny}` placeholders, not encrypted prices. It cannot establish whether
the supplied private keys match. Check TAKU encryption and callback settings,
then verify a genuine callback with resolved fields after entering the Key IDs.

The existing GET `/api/callbacks/taku/reward` endpoint accepts `e_c` (USD),
`e_c_cny` (CNY), and `s_id`. The Android build uses TAKU 6.6.51, which meets
the documented 6.3.68 minimum and 6.4.80 CNY minimum.

Generate the relevant server/client eCPM keys in TAKU Account Information → Key.
Server keys cover S2S bidding and fixed-price sources; client keys cover C2S
bidding. Both kinds of private keys belong exclusively on the backend.

Set `TAKU_ECPM_KEYRING_FILE` to an absolute path outside the web root and Git
repository. Restrict file permissions to the service account. Its JSON format is:

```json
{"238":{"keys":{"KEY_ID_FROM_TAKU":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"}}}
```

Multiple key IDs support source types and key rotation. Keep previous keys until
in-flight callbacks finish. Never send keys to the app or put them in logs.
Restart the service after setting the environment variable. File contents are
read on each verification; replace the complete file atomically when rotating.

Enable encryption in the TAKU console and check the actual callback for `e_c`,
`s_id`, and optionally `e_c_cny`. The documentation describes these as added
callback fields; verify console-supported placeholders before editing the URL.
This implementation does not invent a new MD5 signature formula for these fields.
Existing callback signature validation and session/user/placement checks remain.

Configured games require ciphertext and a recognized key ID. Base64 and RSA
PKCS#1 v1.5 decoding verifies source ID and nonnegative decimal prices. Both
currencies must refer to the same SDK request but their prices are NOT equal.
TAKU SDK RequestId is NOT the backend req_ad_* identifier. A provider request
cannot be reused across sessions of the same game/source. Fixed-price sources
may omit the SDK request ID; no fictitious display binding is claimed for them.

Verification is recorded under `ecpm_verification` in the `taku_reward` event.
Prices are decimal strings with explicit currency. Raw keys are never included in reward events.
RSA encryption alone is not a signature; verification supplements the signed
callback and is not proof of final billable revenue or SDK display identity.

This change verifies encrypted prices; it does NOT change the legacy settlement
formula (`reward_amount / 1000`). Events label this `legacy_reward_amount`.
An unconfigured game without encryption fields retains legacy behavior. A game
with supplied encryption fields but no configured keys receives 503; malformed
or missing required proof receives 602. No wallet writes occur on rejection.
Establish currency, conversion, revenue-share and rounding policies before
changing settlement to encrypted eCPM. Console probes never award coins.

Local tests use generated RSA keys and temporary databases, not live rewards:
`python -m pytest backend/tests/test_taku_callback.py -q`

Deployment and a genuine encrypted TAKU callback remain necessary for acceptance.
