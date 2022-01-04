"""
Update Database
"""
import time
import os
import pathlib
from typing import Any, List, Tuple
from more_itertools import flatten
from more_itertools.more import sort_together
import ray

from modules.db_utils import (
    add_ip_addresses,
    add_malicious_hash_prefixes,
    get_matching_hash_prefix_urls,
    initialise_database,
    add_urls,
    retrieve_malicious_urls,
    retrieve_vendor_prefix_sizes,
    update_malicious_urls,
)
from modules.filewriter import write_db_malicious_urls_to_file
from modules.ray_utils import execute_with_ray
from modules.safebrowsing import SafeBrowsing
from modules.url_utils import (
    get_local_file_url_list,
    get_top10m_url_list,
    get_top1m_url_list,
)


def update_database(
    fetch: bool, identify: bool, retrieve: bool, sources: List[str], vendors: List[str]
) -> None:
    """
    Update Database
    """
    ray.shutdown()
    ray.init(include_dashboard=True)
    update_time = int(time.time())  # seconds since UNIX Epoch

    urls_filenames: List[str] = []
    ips_filenames: List[str] = []

    if "domainsproject" in sources:
        # Scan Domains Project's "domains" directory for local urls_filenames
        local_domains_dir = pathlib.Path.cwd().parents[0] / "domains" / "data"
        local_domains_filepaths: List[str] = []
        for root, _, files in os.walk(local_domains_dir):
            for file in files:
                if file.lower().endswith(".txt"):
                    urls_filenames.append(f"{file[:-4]}")
                    local_domains_filepaths.append(os.path.join(root, file))
        # Sort local_domains_filepaths and urls_filenames by ascending filesize

        local_domains_filesizes: List[int] = [
            os.path.getsize(path) for path in local_domains_filepaths
        ]

        [local_domains_filesizes, local_domains_filepaths, urls_filenames] = [
            list(_)
            for _ in sort_together(
                (local_domains_filesizes, local_domains_filepaths, urls_filenames)
            )
        ]

    if "top1m" in sources:
        urls_filenames.append("top1m_urls")
    if "top10m" in sources:
        urls_filenames.append("top10m_urls")
    if "ipv4" in sources:
        add_ip_addresses_jobs = [
            (f"ipv4_{first_octet}", first_octet) for first_octet in range(2 ** 8)
        ]
        ips_filenames = [_[0] for _ in add_ip_addresses_jobs]

    # Create DB files
    initialise_database(urls_filenames, mode="domains")
    initialise_database(ips_filenames, mode="ips")

    if fetch:
        add_urls_jobs: List[Tuple[Any, ...]] = []
        if "domainsproject" in sources:
            # Extract and Add local URLs to DB
            add_urls_jobs += [
                (get_local_file_url_list, update_time, filename, filepath)
                for filepath, filename in zip(local_domains_filepaths, urls_filenames)
            ]
        if "top1m" in sources:
            # Download and Add TOP1M URLs to DB
            add_urls_jobs.append((get_top1m_url_list, update_time, "top1m_urls"))
        if "top10m" in sources:
            # Download and Add TOP10M URLs to DB
            add_urls_jobs.append((get_top10m_url_list, update_time, "top10m_urls"))
        execute_with_ray(add_urls, add_urls_jobs)

        if "ipv4" in sources:
            # Generate and Add ipv4 addresses to DB
            execute_with_ray(add_ip_addresses, add_ip_addresses_jobs)

    if identify:
        for vendor in vendors:
            safebrowsing = SafeBrowsing(vendor)

            # Download and Update Safe Browsing API Malicious Hash Prefixes to DB
            hash_prefixes = safebrowsing.get_malicious_hash_prefixes()
            add_malicious_hash_prefixes(hash_prefixes, vendor)
            del hash_prefixes  # "frees" memory

        malicious_urls = dict()
        for vendor in vendors:
            safebrowsing = SafeBrowsing(vendor)

            prefix_sizes = retrieve_vendor_prefix_sizes(vendor)

            # Identify URLs in DB whose full Hashes match with Malicious Hash Prefixes
            suspected_urls = set(
                flatten(
                    execute_with_ray(
                        get_matching_hash_prefix_urls,
                        [
                            (filename, prefix_sizes, vendor)
                            for filename in urls_filenames + ips_filenames
                        ],
                    ),
                )
            )

            # To Improve: Store suspected_urls into malicious.db under
            # suspected_urls table columns: [url,Google,Yandex]

            # Among these URLs, identify those with full Hashes
            # found on Safe Browsing API Server
            vendor_malicious_urls = safebrowsing.get_malicious_urls(suspected_urls)
            del suspected_urls  # "frees" memory
            malicious_urls[vendor] = vendor_malicious_urls

        # Write malicious_urls to TXT file
        write_db_malicious_urls_to_file(list(set(flatten(malicious_urls.values()))))

        # TODO push blocklist to GitHub

        # Update malicious URL statuses in DB
        for vendor in vendors:
            execute_with_ray(
                update_malicious_urls,
                [
                    (update_time, vendor, filename)
                    for filename in urls_filenames + ips_filenames
                ],
                store={"malicious_urls": malicious_urls[vendor]},
            )

    if retrieve:
        # Write malicious_urls to TXT file
        write_db_malicious_urls_to_file(retrieve_malicious_urls(urls_filenames))
    ray.shutdown()
