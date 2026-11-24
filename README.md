# Danielhsu--Morning--brief
Morning brief for Macro Economy

## Daily Gemini publication (candidate)

This is a single GitHub Actions producer, scheduled at 08:00 Asia/Taipei after activation. It retains the existing six interactive sections, embedded JSON, archive navigation, and public site address. The manual Windows publisher remains in the tree and must not write concurrently with automation. The retired Dot scheduler must remain off.

Offline validation (no secret or Gemini): `python -B -m unittest discover -s scripts -p "test_*.py" -v`.

Before activation, the repository owner must confirm:

1. Pages **Settings → Pages → Build and deployment → Source → GitHub Actions**; the existing site URL does not change. Branch-source deployment cannot be relied on for the generator's `GITHUB_TOKEN` push.
2. Configure Actions *secret name only* `GEMINI_API_KEY` using the already authorized Google project, and Actions variable `GEMINI_MODEL` using the chosen model. Never paste a key into code, terminal output, an issue, or chat. Check authorized spend and permitted public market-data reuse before enabling.
3. Confirm source coverage on a real 08:00 run: NYSE and TWSE completed dates can differ. The current collector verifies TAIEX, and optionally Treasury 2Y/10Y/30Y/2s10s and the TAIFEX night last transaction (not settlement). It deliberately does not fetch or publish FRED's copyrighted S&P 500 data. The tested UI fallback is a blank value plus link, with no carryover. No NYSE calendar beyond 2028 is assumed. Full acceptance is blocked before any Gemini request: the original dashboard has 24 cross-asset rows, 10 macro cards, 7 US and 5 Taiwan company rows, 16 Taiwan market fields, 8 supply-chain segments, 5 Taiwan signals, and a scenario/event module; collection currently covers at most 6/24 cross-asset values and does not supply company, full macro, or event inputs. Production source adapters and binding/quality tests must be completed before turning it on. No metered Search grounding.
4. Leave `MORNING_BRIEF_AUTOMATION_ENABLED` unset until these prerequisites clear. After setting it to `true`, manual workflow dispatch with **publish** selected runs the same production path; an ordinary manual run only performs offline checks. Same-day reruns do not regenerate or overwrite an archive. After deploying, the workflow verifies the exact latest JSON digest, identical dated JSON and embedded homepage/archive data, and manifest date/cutoff/links. On a post-push deployment failure inspect the existing deployment and commit without rerunning Gemini.
