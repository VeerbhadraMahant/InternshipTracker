# Internship Tracker

A free tracker for software, CS and AI internships in Pune, Mumbai and remote. Every two hours a
GitHub Action checks a watchlist of companies' own hiring systems and a few trusted remote job feeds.
It keeps the internships, works out who can apply to each one, and sends an email and a Discord
message when a new role matches your filters. The dashboard is a static site on Cloudflare Workers.

There are no servers, no database and no paid APIs. The job data lives in the repo as JSON.

```
GitHub Actions (cron, every 2h)
  └─ tracker/run.py
       ├─ sources/   Greenhouse · Lever · Ashby · SmartRecruiters · Workday   (company watchlist)
       │             RemoteOK · Remotive · We Work Remotely · HN "Who is hiring"  (feeds)
       ├─ classify/  internship? · field · location · eligibility · stipend
       ├─ store.py   data/jobs.json, data/seen.json, data/status.json  → committed
       └─ alerts/    Discord webhook + email digest, new matches only
Cloudflare Workers  ← wrangler deploys _site/ (web/ + data/*.json)   (filtering runs in the browser)
```

## How roles are tagged

| Tag | Values |
|---|---|
| Location | `pune`, `mumbai`, `india`, `remote`, `other`. Pune includes Hinjewadi, Kharadi, Baner and nearby areas; Mumbai includes Navi Mumbai, Thane and Powai. |
| Field | `software`, `ai-ml`, `data`, `other`, read from the title, or from the description if the title is vague. |
| Eligibility | `india-ok`, `open-worldwide`, `unknown`, `timezone`, `needs-work-auth`, `restricted`, `onsite-abroad` |
| Stipend | Converted to ₹ per month from text like `₹25,000/month`, `6 LPA`, `$20/hr` or `€1,500 monthly`, or from the ATS's own pay field. Otherwise "not disclosed". |

The eligibility check is conservative. A remote role counts as open only when the posting says so.
If the posting doesn't mention location limits, the role is `unknown`. Each verdict keeps the phrase
it was based on, and clicking a row on the dashboard shows it, for example "Candidates must be
located in the United States".

## Setup

This takes about fifteen minutes. You need a free Cloudflare account.

1. Merge into `main`. GitHub only runs scheduled workflows from the default branch.
2. In the Cloudflare dashboard, open Workers & Pages once. The first visit asks you to pick a
   `workers.dev` subdomain. Your site will live at `https://internship-tracker.<subdomain>.workers.dev`.
3. Create an API token: My Profile → API Tokens → Create Token → use the "Edit Cloudflare Workers"
   template and scope it to your account. Copy the token, because Cloudflare shows it only once.
4. Find your Account ID under Workers & Pages → Overview, in the right-hand column. `npx wrangler whoami` also prints it.
5. In GitHub, add these under Settings → Secrets and variables → Actions → Secrets. The tracker skips
   any alert channel whose secrets are missing.

   | Secret | Value |
   |---|---|
   | `CLOUDFLARE_API_TOKEN` | The token from step 3 |
   | `CLOUDFLARE_ACCOUNT_ID` | The ID from step 4 |
   | `DISCORD_WEBHOOK_URL` | In Discord: Server settings → Integrations → Webhooks → New webhook → Copy URL |
   | `SMTP_USER` | Your Gmail address |
   | `SMTP_APP_PASSWORD` | Google Account → Security → 2-Step Verification → App passwords (16 characters) |
   | `ALERT_EMAIL_TO` | The address that receives alerts (can be the same one) |

   For another mail provider, also set `SMTP_HOST` and `SMTP_PORT` (SSL) in the workflow env.
6. On the Variables tab, add `DASHBOARD_URL` with your workers.dev URL. Alerts link to it.
7. Run Actions → Deploy → Run workflow to publish the dashboard. It will be empty until the first scrape.
8. Run Actions → Scrape → Run workflow. The first run records every current role as seen and sends
   nothing, so you don't get hundreds of alerts. When it finishes, Deploy runs again with the data.
9. Open your workers.dev URL and check the Source health panel at the bottom for watchlist entries
   that fail (see the first caveat below).

## How the Cloudflare part works

The dashboard is a Cloudflare Worker with no code of its own. It uses Workers static assets:
Cloudflare stores the files in `_site/` and serves them from its edge network, close to whoever
opens the page. Requests for static files don't run Worker code, so they are free and don't count
toward the free plan's 100,000 requests a day.

- `wrangler.jsonc` is the Worker's config. `build.command` runs `scripts/build_site.sh`, which copies
  `web/` and `data/*.json` into `_site/`, and `assets.directory` tells Cloudflare to serve that folder.
- `web/_headers` sets response headers. The data files get `max-age=0, must-revalidate`, so a
  reload always shows the latest roles. Cloudflare reads this file but doesn't serve it.
- `.github/workflows/deploy.yml` runs `wrangler deploy` with your API token. It runs on pushes to
  `main` that change the site, and after every Scrape run. Wrangler only uploads files whose
  content changed, so a run with no new data uploads almost nothing.
- Every deploy creates a new version. Workers & Pages → internship-tracker → Deployments lists
  them, and you can roll back to an older one from there.

To try it locally (needs Node 18 or newer):

```bash
npx wrangler login                 # opens a browser to authorize your account
npx wrangler dev                   # builds _site/ and serves it at http://localhost:8787 on Cloudflare's runtime
npx wrangler deploy --dry-run      # checks the config and lists what would upload, without deploying
npx wrangler deploy                # deploys from your machine, same as the Deploy workflow
npx wrangler tail                  # streams live request logs from the deployed Worker
```

Next steps that fit this project, if you want to go further:

- Add a Worker script (`"main": "src/index.js"` in `wrangler.jsonc`) for routes like `/api/jobs?loc=pune`.
  Static files are still served first, and the script only runs for paths that aren't files.
- Move `data/*.json` out of git into Workers KV or R2, and have the scraper upload there instead of committing.
- Attach a custom domain under the Worker's Settings → Domains & Routes.

## Configuration

`config/watchlist.yaml` lists the companies to watch. Its header explains how to get each ATS slug from a careers page URL.

`config/filters.yaml` decides which new roles send an alert: locations, fields, eligibility, minimum
stipend, and whether roles with no stated stipend count. The dashboard has separate filters. It saves
them in the URL, so you can bookmark a view.

## Running locally

```bash
pip install -r requirements-dev.txt
python -m pytest -q                               # parsers + classifiers + runner
python -m tracker.run --dry-run                   # fetch & classify everything, write nothing, alert nothing
python -m tracker.run --dry-run --only greenhouse:druva   # one source
python -m tracker.run --test-alert                # send one sample alert (needs the env vars above)
npx wrangler dev                                  # dashboard at http://localhost:8787
```

## Caveats

1. The watchlist slugs are unverified. I wrote them without network access to the job APIs, so some
   will be wrong or out of date. A bad entry fails on its own without stopping the run, and it shows up
   in the Source health panel and the Actions log. Fix or delete those entries after the first run.
2. Pune and Mumbai coverage depends on the watchlist. Greenhouse, Lever and Ashby are mostly used by
   US and European startups. Most MNCs hire for their Indian offices through Workday, which is
   supported, or through SuccessFactors, Darwinbox, Taleo and custom portals. Those need fragile HTML
   scraping, so they aren't supported. Adding Workday tenants of companies with Pune or Mumbai
   offices helps most.
3. "Every two hours" is approximate. GitHub starts scheduled runs late when it is busy, sometimes by
   30 minutes or more, and occasionally skips one. That is still hours or days ahead of the aggregators.
4. GitHub disables scheduled workflows after 60 days without repo activity. The data commits count as
   activity, but if nothing changes for 60 days, re-enable Scrape from the Actions tab.
5. The remote feeds mostly list full-time roles. The tracker keeps only internships, so expect a few
   hits a week from them. HN posts one hiring thread a month and is checked every 12 hours. Remotive
   is checked every 6 hours because its API terms ask for infrequent polling.
6. The classifiers are keyword rules and will miss some cases. The saved evidence phrase lets you
   check any verdict, and `tests/test_classify.py` pins the current behavior. When you find a miss,
   add it there as a test case.
7. Currency conversion uses fixed approximate rates, set in `tracker/classify/stipend.py`. The
   dashboard always shows the original figure next to the ₹ estimate.

## Layout

```
tracker/     models, http, config, store, run, sources/, classify/, alerts/
config/      watchlist.yaml, filters.yaml
web/         index.html, app.js, tokens.css (design tokens), styles.css
data/        jobs.json, seen.json, status.json   (written by the Scrape workflow)
scripts/     build_site.sh (assembles _site/ for deploys)
wrangler.jsonc  Cloudflare Worker config
tests/       pytest suite
```

The design follows the Harvest style from refero.design: a warm cream background, white cards, a serif
headline, and orange used only for actions, the active filter and new roles. All design tokens are in
`web/tokens.css`. The original fonts are commercial, so Inter and Newsreader stand in for them.
