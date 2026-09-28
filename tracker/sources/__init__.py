from . import ashby, greenhouse, hn, lever, remoteok, remotive, smartrecruiters, workday, wwr

# Company ATS fetchers: fetch(Company) -> list[Job]
ATS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
}

# Aggregate feeds: fetch(feed_config: dict) -> list[Job]
FEEDS = {
    "remoteok": remoteok.fetch,
    "remotive": remotive.fetch,
    "weworkremotely": wwr.fetch,
    "hn-whoishiring": hn.fetch,
}
