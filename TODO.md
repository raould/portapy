You're right that static checking can't do it alone. portapy's own README already says a clean check "does not prove that the code runs." But you don't have to give up the fast loop. The goal is to keep almost all code under fast static checks and make the dynamic part small and cheap.

**1. Don't skip portapy on adapters; give them a different profile.** Adapters still have to parse on every version, so all of portapy's syntax rules still apply to them. Only the import allowlist relaxes, chosen by path (`adapters/` gets its own list, for example `hashlib`, `md5`, `binascii`, `socket`, `select`). You keep static checking of syntax in the risky code and drop only the one rule that can't apply there.

**2. Make the bytes/text boundary a static rule for application code.** This is what makes the static check meaningful again. Outside `adapters/`, forbid the operations where the silent traps live:
- `.encode(` / `.decode(`, `binascii`, `struct`
- `open(`, `socket`, `os.listdir`, `os.lstat`
- comparisons with `''`, which is how `b'' == ''` fails silently
- `str(` called on anything an adapter didn't return

These are simple lexical or AST checks, like portapy's existing ones. Once they pass, the application code does no string/bytes conversion at all; it only passes along values that adapters hand it. The silent-failure class is then confined to the adapters, and those are what the dynamic tests cover.

**3. Make dynamic testing cheap where it's needed, and rare where it's expensive.**

| When | What runs | Cost |
|---|---|---|
| Every save | portapy static checks, both profiles | Seconds |
| Every commit | Adapter unit tests on two local interpreters (e.g. 2.7 and 3.x) | Seconds |
| Adapter change | Adapter unit tests in every Docker image, in parallel | About a minute |
| Nightly or pre-merge | Full app end-to-end on the filename corpus, every image | Long, but unattended |

Two things keep the middle tiers fast:
- **Adapter tests are tiny unit tests:** known vectors and type assertions, milliseconds each. The time goes into starting containers, so keep one container per image running and send it all the tests.
- **Cache results** by a hash of the adapter files plus the image digest. If neither changed, skip that image.

**4. Accept the remaining risk where it belongs.** The full matrix is the only real proof, as you say. But with the boundary rule in place, a change to application code can't introduce a version-specific bytes/text bug, so the slow tests mainly guard against changes to adapters, which happen rarely. Adapters will churn early in a project, then settle. After that, the day-to-day loop is mostly static checks plus a two-interpreter test run.
