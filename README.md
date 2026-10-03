# Internship Tracker

A free tracker for software, CS and AI internships in Pune, Mumbai and remote. Twice a day a
GitHub Action checks a watchlist of companies' own hiring systems, careers pages read through
Firecrawl, and a few trusted remote job feeds. A weekly Firecrawl search adds more companies.
It keeps the internships, works out who can apply to each one, and sends an email and a Discord
message when a new role matches your filters. The dashboard is a static site on Cloudflare Workers.

There are no servers and no database, and everything runs on free tiers. The job data lives in the repo as JSON.

```
GitHub Actions (cron, every 12h; Discover weekly)
  └─ tracker/run.py
       ├─ sources/   Greenhouse · Lever · Ashby · SmartRecruiters · Workday   (company watchlist)
       │             careers pages via Firecrawl                              (no public API)
       │             RemoteOK · Remotive · We Work Remotely · HN "Who is hiring"  (feeds)
       ├─ classify/  internship? · field · location · eligibility · stipend
       ├─ store.py   data/jobs.json, data/seen.json, data/status.json  → committed
       └─ alerts/    Discord webhook + email digest, new matches only
Cloudflare Workers  ← rebuilds _site/ (web/ + data/*.json) on every push to main   (filtering runs in the browser)
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

Live dashboard: https://internshiptracker.mahantveerbhadra596.workers.dev

To set up your own copy (about ten minutes, free Cloudflare account):

1. Merge into `main`. GitHub only runs scheduled workflows from the default branch.
2. In the Cloudflare dashboard, go to Workers & Pages → Create → Import a repository. Connect GitHub,
   allow access to this repo and select it.
3. Use these build settings:
   - Project name: the `name` in `wrangler.jsonc` (`internshiptracker`). If you pick a different
     name, change `wrangler.jsonc` to match, or the build fails.
   - Production branch: `main`
   - Build command: leave empty
   - Deploy command: `npx wrangler deploy`
4. Save and Deploy. When the build finishes, Cloudflare shows the site's `workers.dev` URL.
5. In GitHub, add alert secrets under Settings → Secrets and variables → Actions → Secrets. The
   tracker skips any alert channel whose secrets are missing.

   | Secret | Value |
   |---|---|
   | `DISCORD_WEBHOOK_URL` | In Discord: Server settings → Integrations → Webhooks → New webhook → Copy URL |
   | `SMTP_USER` | Your Gmail address |
   | `SMTP_APP_PASSWORD` | Google Account → Security → 2-Step Verification → App passwords (16 characters) |
   | `ALERT_EMAIL_TO` | The address that receives alerts (can be the same one) |
   | `FIRECRAWL_API_KEY` | firecrawl.dev → API Keys. Needed for discovery and careers pages |

   For another mail provider, also set `SMTP_HOST` and `SMTP_PORT` (SSL) in the workflow env.
6. On the Variables tab, add `DASHBOARD_URL` with your `workers.dev` URL. Alerts link to it.
7. Run Actions → Scrape → Run workflow, or wait for the next scheduled run. The first run records
   every current role as seen and sends nothing, so you don't get hundreds of alerts. It commits
   the data to `main`, and Cloudflare rebuilds the site from that commit.
8. Open the site and check the Source health panel at the bottom for watchlist entries that fail.

## How the Cloudflare part works

The dashboard is a Cloudflare Worker with no code of its own. It uses Workers static assets:
Cloudflare stores the files in `_site/` and serves them from its edge network, close to whoever
opens the page. Requests for static files don't run Worker code, so they are free and don't count
toward the free plan's 100,000 requests a day.

- Cloudflare's Git integration (Workers Builds) watches `main`. Every push, including the scraper's
  data commits, starts a build that runs `npx wrangler deploy`. No API tokens or GitHub secrets are
  involved. Builds are listed under Workers & Pages → internshiptracker → Deployments, and you can
  roll back to an older version from there.
- `wrangler.jsonc` is the Worker's config. `build.command` runs `scripts/build_site.sh`, which copies
  `web/` and `data/*.json` into `_site/`, and `assets.directory` tells Cloudflare to serve that folder.
- `web/_headers` sets response headers. The data files get `max-age=0, must-revalidate`, so a
  reload always shows the latest roles. Cloudflare reads this file but doesn't serve it.

To try it locally (needs Node 18 or newer):

```bash
npx wrangler dev                   # builds _site/ and serves it at http://localhost:8787 on Cloudflare's runtime
npx wrangler deploy --dry-run      # checks the config and lists what would upload, without deploying
npx wrangler login                 # only needed for the next two
npx wrangler deploy                # deploys from your machine instead of waiting for a push
npx wrangler tail                  # streams live request logs from the deployed Worker
```

Next steps that fit this project, if you want to go further:

- Add a Worker script (`"main": "src/index.js"` in `wrangler.jsonc`) for routes like `/api/jobs?loc=pune`.
  Static files are still served first, and the script only runs for paths that aren't files.
- Move `data/*.json` out of git into Workers KV or R2, and have the scraper upload there instead of committing.
- Attach a custom domain under the Worker's Settings → Domains & Routes.

## How Firecrawl is used

Firecrawl does two jobs, and both stay inside its free tier (1,000 credits a month). A page fetch
costs 1 credit, AI extraction adds 4, and a search costs 2 credits per 10 results.

1. **Finding more companies (weekly).** The Discover workflow runs the searches listed under
   `discovery` in `config/watchlist.yaml`, such as `site:jobs.lever.co intern India`. Every job-board
   link it finds is turned into a company (Greenhouse, Lever, Ashby, SmartRecruiters or Workday) and
   checked against that board's free API. Boards that answer with at least one posting go into
   `config/discovered.yaml`, and from then on they cost nothing. Eight queries of 20 results use
   about 32 credits a week. At most 25 companies are added per run. Delete an entry to stop
   tracking it.
2. **Careers pages with no public API (twice a day).** Entries with `ats: careerpage` are fetched
   as markdown for 1 credit. If the page hasn't changed since the last run, that's all it costs. If
   it has, the tracker pulls internship links out of the markdown. Only when the page mentions
   interns but has no such links does it pay for Firecrawl's AI extraction. Plan on about 60 credits
   a month per page, so roughly 10 to 12 pages fit next to discovery.

Credits are counted in `data/firecrawl_state.json`, and Firecrawl calls stop at 900 a month
(change it with the `FIRECRAWL_MONTHLY_BUDGET` repo variable). When the budget runs out or the key
is missing, the Firecrawl parts are skipped and every other source keeps working. The Source
health panel shows the month's usage.

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

1. Job boards move. Every hand-picked entry answered on the first live run, and discovered ones are
   checked when they're added, but a company can rename or close its board later. A bad entry fails
   on its own without stopping the run and shows up in the Source health panel and the Actions log.
2. Pune and Mumbai coverage depends on the watchlist. Greenhouse, Lever and Ashby are mostly used by
   US and European startups. Most MNCs hire for their Indian offices through Workday, which is
   supported, or through SuccessFactors, Darwinbox, Taleo and custom portals. Those can be added as
   `careerpage` entries read through Firecrawl, but each one costs credits, so pick the companies
   you care about most. Weekly discovery adds Workday and other boards, which are free after the search.
3. Runs happen twice a day (00:17 and 12:17 UTC), and the times are approximate. GitHub starts
   scheduled runs late when it is busy, sometimes by 30 minutes or more, and occasionally skips one.
4. GitHub disables scheduled workflows after 60 days without repo activity. The data commits count as
   activity, but if nothing changes for 60 days, re-enable Scrape from the Actions tab.
5. The remote feeds mostly list full-time roles. The tracker keeps only internships, so expect a few
   hits a week from them. HN posts one hiring thread a month and is checked once a day. Remotive
   is checked every 6 hours because its API terms ask for infrequent polling.
6. The classifiers are keyword rules and will miss some cases. The saved evidence phrase lets you
   check any verdict, and `tests/test_classify.py` pins the current behavior. When you find a miss,
   add it there as a test case.
7. Currency conversion uses fixed approximate rates, set in `tracker/classify/stipend.py`. The
   dashboard always shows the original figure next to the ₹ estimate.

## Layout

```
tracker/     models, http, config, store, run, sources/, classify/, alerts/
config/      watchlist.yaml, filters.yaml, discovered.yaml (written by the Discover workflow)
web/         index.html, app.js, tokens.css (design tokens), styles.css
data/        jobs.json, seen.json, status.json   (written by the Scrape workflow)
scripts/     build_site.sh (assembles _site/ for deploys)
wrangler.jsonc  Cloudflare Worker config
tests/       pytest suite
```

The design follows the Harvest style from refero.design: a warm cream background, white cards, a serif
headline, and orange used only for actions, the active filter and new roles. All design tokens are in
`web/tokens.css`. The original fonts are commercial, so Inter and Newsreader stand in for them.
