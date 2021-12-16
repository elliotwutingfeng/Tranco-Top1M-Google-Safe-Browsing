## This script demonstrates the basic features of the database
import ray
import time

from db_utils import (
add_maliciousHashPrefixes,
identify_suspected_urls,
initialise_database,
add_URLs,
update_malicious_URLs,
update_activity_URLs
)
from alivecheck import check_activity_URLs
from filewriter import write_all_malicious_urls_to_file
from safebrowsing import SafeBrowsing
from url_utils import get_top10m_url_list, get_top1m_url_list

def update_database():
    ray.shutdown()
    ray.init(include_dashboard=False)
    conn = initialise_database()
    updateTime = time.time()
    
    # Download and Add TOP1M and TOP10M URLs to DB
    top1m_urls = get_top1m_url_list()
    add_URLs(conn, top1m_urls, updateTime)
    del top1m_urls
    top10m_urls = get_top10m_url_list()
    add_URLs(conn, top10m_urls, updateTime)
    del top10m_urls

    malicious_urls = set()
    for vendor in ["Google","Yandex"]:
        sb = SafeBrowsing(vendor)

        # Download and Update Safe Browsing API Malicious Hash Prefixes to DB
        hash_prefixes = sb.get_malicious_hash_prefixes()
        add_maliciousHashPrefixes(conn, hash_prefixes, vendor)
        del hash_prefixes # "frees" memory
        
        # Identify URLs in DB whose full Hashes match with Malicious Hash Prefixes
        suspected_urls = identify_suspected_urls(conn, vendor)

        # Among these URLs, identify those with full Hashes are found on Safe Browsing API Server
        vendor_malicious_urls = sb.get_malicious_URLs(suspected_urls)
        del suspected_urls # "frees" memory

        malicious_urls.update(vendor_malicious_urls)
        
        # Update vendor_malicious_urls to DB
        update_malicious_URLs(conn, vendor_malicious_urls, updateTime, vendor)

    # Write malicious_urls to TXT file (overwrites existing TXT file)
    malicious_urls = list(malicious_urls)
    write_all_malicious_urls_to_file(malicious_urls)

    # Check host statuses of URLs with fping and update host statuses to DB
    #alive_and_not_dns_blocked_urls,alive_and_dns_blocked_urls,_,_,_ = check_activity_URLs(malicious_urls)
    #update_activity_URLs(conn, alive_and_not_dns_blocked_urls+alive_and_dns_blocked_urls, updateTime)

    # push to GitHub
    # TODO
    
    ray.shutdown()

if __name__=='__main__':
    update_database()