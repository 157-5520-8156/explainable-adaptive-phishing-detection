"""Deterministic URL-only features. No target, HTML, DNS, or network access."""
import ipaddress
import math
from collections import Counter
from urllib.parse import urlsplit

import tldextract

PSL = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True, cache_dir=None)
TOKENS = ("login", "verify", "account", "secure", "update", "password", "bank", "signin")

def parse_url(url):
    raw = str(url).strip()
    try:
        p = urlsplit(raw if "://" in raw else "http://" + raw)
        host = (p.hostname or "").lower().rstrip(".")
    except ValueError:
        return raw, None, ""
    return raw, p, host

def canonical_url(url):
    raw, p, host = parse_url(url)
    if not p or not host:
        return ""
    # Case-normalize only scheme and authority. Path/query remain case-sensitive.
    return p._replace(scheme=p.scheme.lower(), netloc=p.netloc.lower(), fragment="").geturl()

def domain_group(url):
    raw, p, host = parse_url(url)
    if not host:
        return ""
    e = PSL(host)
    return e.top_domain_under_public_suffix or host

def features(url):
    raw, p, host = parse_url(url)
    path, query = (p.path, p.query) if p else ("", "")
    n = max(len(raw), 1)
    counts = Counter(raw)
    entropy = -sum((v / n) * math.log2(v / n) for v in counts.values())
    try:
        ipaddress.ip_address(host)
        is_ip = 1
    except ValueError:
        is_ip = 0
    e = PSL(host) if host else None
    out = {
        "url_length": len(raw), "host_length": len(host), "path_length": len(path),
        "query_length": len(query), "fragment_length": len(p.fragment) if p else 0,
        "digit_ratio": sum(c.isdigit() for c in raw)/n,
        "letter_ratio": sum(c.isalpha() for c in raw)/n,
        "special_ratio": sum(not c.isalnum() for c in raw)/n,
        "entropy": entropy, "unique_char_ratio": len(counts)/n,
        "host_digit_ratio": sum(c.isdigit() for c in host)/max(len(host), 1),
        "host_hyphens": host.count("-"), "subdomain_count": len(e.subdomain.split(".")) if e and e.subdomain else 0,
        "suffix_length": len(e.suffix) if e else 0,
        "path_depth": sum(bool(x) for x in path.split("/")),
        "query_parameters": query.count("&") + 1 if query else 0,
        "has_https": int(bool(p) and p.scheme.lower()=="https"),
        "host_is_ip": is_ip, "has_userinfo": int(bool(p) and "@" in p.netloc),
        "has_punycode": int("xn--" in host),
    }
    for char, name in [(".","dots"),("-","hyphens"),("_","underscores"),("/","slashes"),("?","questions"),("=","equals"),("&","ampersands"),("%","percents"),("@","ats")]:
        out[name] = raw.count(char)
    lower = raw.lower()
    out["suspicious_token_count"] = sum(lower.count(t) for t in TOKENS)
    return out
