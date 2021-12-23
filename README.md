# Safe Browsing DNSBL (Domain Name System-based blackhole list) Generator

## Overview

Create and/or update local [SQLite](https://www.sqlite.org) databases with URLs sourced from various public lists (e.g. Tranco TOP1M), and use the Google Safe Browsing API and Yandex Safe Browsing API to generate a malicious URL blocklist for [DNSBL](https://en.wikipedia.org/wiki/Domain_Name_System-based_blackhole_list) applications like [pfBlockerNG](https://linuxincluded.com/block-ads-malvertising-on-pfsense-using-pfblockerng-dnsbl) or [Pi-hole](https://pi-hole.net).

Uses [Ray](http://www.ray.io) to make parallel requests with pipelining to the Safe Browsing APIs.

## URL sources

- Domains Project: https://domainsproject.org
- DomCop TOP10M : https://www.domcop.com/top-10-million-domains
- Tranco TOP1M : https://tranco-list.eu

## Requirements

- Linux or macOS
- Tested on Python 3.8.12
- x86-64 CPU; for Python Ray support
- Recommended: At least 8GB RAM
- Recommended: At least 5GB storage space
- [Obtain a Google Developer API key and set it up for the Safe Browsing API](https://developers.google.com/safe-browsing/v4/get-started)
- [Obtain a Yandex Developer API key](https://yandex.com/dev/safebrowsing)

## Setup instructions

`git clone` and `cd` into the project directory, then run the following

```bash
echo "GOOGLE_API_KEY=<your-google-api-key-here>" >> .env
echo "YANDEX_API_KEY=<your-yandex-api-key-here>" >> .env
pip3 install -r requirements.txt
```

## How to use

```bash
# fetch mode: Update local databases with latest TOP1M+TOP10M URLs and generate blocklist (stored in blocklists/ folder) from local databases
python3 main.py --mode fetch --lists top1m top10m domainsproject everything
# generate mode: Generate blocklist (stored in blocklists/ folder) based on last 1500 URLs from Tranco TOP1M list
python3 main.py --mode generate --lists top1m top10m domainsproject everything
# fetch_and_generate mode: Generate blocklist (stored in blocklists/ folder) based on last 1500 URLs from Tranco TOP1M list
python3 main.py --mode fetch_and_generate --lists top1m top10m domainsproject everything
```

## Known Issues

- Yandex Safe Browsing API calls often fail with either ConnectionResetError or HTTP Status Code 204. Yandex Technical support has been notified. _Temporary workaround: Keep retrying API call until it succeeds_

## User Protection Notice

### Google

Google works to provide the most accurate and up-to-date information about unsafe web resources. However, Google cannot guarantee that its information is comprehensive and error-free: some risky sites may not be identified, and some safe sites may be identified in error.

## References

- https://developers.google.com/safe-browsing
- https://developers.google.com/safe-browsing/v4/usage-limits
- https://yandex.com/dev/safebrowsing/
- https://tranco-list.eu
- https://www.domcop.com/top-10-million-domains
- https://remusao.github.io/posts/few-tips-sqlite-perf.html
- https://domainsproject.org