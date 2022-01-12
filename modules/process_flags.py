"""
Process flags
"""
import time
from typing import Dict
from more_itertools import flatten
import ray

from modules.database.select import (
    retrieve_matching_hash_prefix_urls,
    retrieve_malicious_urls,
    retrieve_vendor_hash_prefix_sizes,
)
from modules.database.create_table import initialise_databases
from modules.database.insert import (
    add_urls,
    add_ip_addresses,
    replace_malicious_url_hash_prefixes,
)
from modules.database.update import update_malicious_urls

from modules.filewriter import write_urls_to_txt_file
from modules.utils.parallel_compute import execute_with_ray
from modules.safebrowsing import SafeBrowsing

from modules.feeds.top1m import Top1M
from modules.feeds.top10m import Top10M
from modules.feeds.cubdomain import CubDomain
from modules.feeds.domainsproject import DomainsProject
from modules.feeds.ipv4 import Ipv4

def process_flags(parser_args: Dict) -> None:
    # pylint: disable=too-many-locals
    """Run DNSBL generator tasks in sequence based on `parser_args` flags set by user.

    Args:
        parser_args (Dict): Flags set by user; see `main.py` for more details
    """
    ray.shutdown()
    ray.init(include_dashboard=True, num_cpus=parser_args["num_cpus"])
    update_time = int(time.time())  # seconds since UNIX Epoch

    top1m = Top1M(parser_args,update_time)
    top10m = Top10M(parser_args,update_time)
    cubdomain = CubDomain(parser_args,update_time)
    domainsproject = DomainsProject(parser_args,update_time)

    domains_db_filenames = (
        top1m.db_filename
        + top10m.db_filename
        + cubdomain.db_filenames
        + domainsproject.db_filenames
    )

    ipv4 = Ipv4(parser_args)

    # Create database files
    initialise_databases(domains_db_filenames, mode="domains")
    initialise_databases(ipv4.db_filenames, mode="ips")

    execute_with_ray(add_urls, top1m.jobs + top10m.jobs + cubdomain.jobs + domainsproject.jobs)
    execute_with_ray(add_ip_addresses, ipv4.jobs)

    if parser_args["identify"]:
        malicious_urls = dict()
        for vendor in parser_args["vendors"]:
            safebrowsing = SafeBrowsing(vendor)

            if not parser_args["use_existing_hashes"]:
                # Download and Update Safe Browsing API Malicious URL hash prefixes to database
                replace_malicious_url_hash_prefixes(
                    safebrowsing.get_malicious_url_hash_prefixes(), vendor
                    )

            prefix_sizes = retrieve_vendor_hash_prefix_sizes(vendor)

            # Identify URLs in database whose full Hashes match with Malicious URL hash prefixes
            suspected_urls = set(
                flatten(
                    execute_with_ray(
                        retrieve_matching_hash_prefix_urls,
                        [
                            (filename, prefix_sizes, vendor)
                            for filename in domains_db_filenames + ipv4.db_filenames
                        ],
                    ),
                )
            )

            # Among these URLs, identify those with full Hashes
            # found on Safe Browsing API Server
            vendor_malicious_urls = safebrowsing.get_malicious_urls(suspected_urls)
            del suspected_urls  # "frees" memory
            malicious_urls[vendor] = vendor_malicious_urls

        write_urls_to_txt_file(list(set(flatten(malicious_urls.values()))))

        # TODO push blocklist to GitHub

        # Update malicious URL statuses in database
        for vendor in parser_args["vendors"]:
            execute_with_ray(
                update_malicious_urls,
                [
                    (update_time, vendor, filename)
                    for filename in domains_db_filenames + ipv4.db_filenames
                ],
                task_obj_store_args={"malicious_urls": malicious_urls[vendor]},
            )

    if parser_args["retrieve"]:
        write_urls_to_txt_file(retrieve_malicious_urls(domains_db_filenames))
    ray.shutdown()
