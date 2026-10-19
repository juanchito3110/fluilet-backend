"""Audit installed package names/versions against OSV; never send application data."""

import importlib.metadata
import json
import urllib.request


def audit(packages, fetch):
    payload = {
        "queries": [
            {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
            for name, version in packages
        ]
    }
    result = fetch(payload)
    if not isinstance(result.get("results"), list) or len(result["results"]) != len(packages):
        raise ValueError("Incomplete advisory response")
    return [
        {"package": name, "version": version, "advisories": [v["id"] for v in item["vulns"]]}
        for (name, version), item in zip(packages, result["results"], strict=True)
        if item.get("vulns")
    ]


def fetch_osv(payload):
    request = urllib.request.Request(
        "https://api.osv.dev/v1/querybatch",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    packages = sorted(
        (distribution.metadata["Name"], distribution.version)
        for distribution in importlib.metadata.distributions()
    )
    try:
        affected = audit(packages, fetch_osv)
    except Exception:
        print(json.dumps({"status": "unavailable", "audited": 0}))
        return 2
    print(
        json.dumps(
            {
                "status": "affected" if affected else "ok",
                "audited": len(packages),
                "affected": affected,
            }
        )
    )
    return 1 if affected else 0


if __name__ == "__main__":
    raise SystemExit(main())
