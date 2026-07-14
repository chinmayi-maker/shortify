#!/usr/bin/env python3
import sys
import requests

def shorten_with_isgd(long_url):
    try:
        r = requests.get(
            "https://is.gd/create.php",
            params={"format": "simple", "url": long_url},
            timeout=5
        )
        if r.status_code == 200:
            short = r.text.strip()
            if short.startswith("http"):
                return short
    except Exception as e:
        print("Error:", e)
    return None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python shorten_cli.py <long_url>")
        sys.exit(1)
    long = sys.argv[1]
    short = shorten_with_isgd(long)
    if short:
        print(short)
    else:
        print("Failed to shorten URL")
