#!/usr/bin/env python3
"""Inject idempotent personal rules into a generated Shadowrocket profile."""

import argparse
import json
import re
from pathlib import Path

START = "# >>> PERSONALIZED APPLE RULES >>>"
END = "# <<< PERSONALIZED APPLE RULES <<<"


def remove_rule(text: str, kind: str, value: str, policy: str) -> str:
    pattern = rf"(?im)^{re.escape(kind)},{re.escape(value)},{re.escape(policy)}\r?\n"
    return re.sub(pattern, "", text)


def set_general_option(text: str, name: str, value: str) -> str:
    pattern = rf"(?im)^{re.escape(name)}\s*=.*$"
    replacement = f"{name} = {value}"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise SystemExit(f"Missing [General] option: {name}")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rules = args.rules.read_text(encoding="utf-8")

    for name, value in config.get("general_overrides", {}).items():
        rules = set_general_option(rules, name, value)

    rules = re.sub(rf"(?ms)^{re.escape(START)}\r?\n.*?^{re.escape(END)}\r?\n?", "", rules)
    for domain in config["direct"]:
        rules = remove_rule(rules, "DOMAIN-SUFFIX", domain, "DIRECT")
    for domain in config["proxy"]:
        rules = remove_rule(rules, "DOMAIN-SUFFIX", domain, "PROXY")
    for item in config["reject_drop"]:
        rules = remove_rule(rules, item["kind"], item["value"], "REJECT-DROP")
    for domain in config["remove_conflicting_proxy"]:
        rules = remove_rule(rules, "DOMAIN-SUFFIX", domain, "Proxy")
        rules = remove_rule(rules, "DOMAIN-SUFFIX", domain, "PROXY")

    section = [START, "# Apple Weather and Location: direct connection"]
    section += [f"DOMAIN-SUFFIX,{domain},DIRECT" for domain in config["direct"]]
    section += ["", "# Apple Weather QUIC fallback"]
    section += [f"{item['kind']},{item['value']},REJECT-DROP" for item in config["reject_drop"]]
    section += ["", "# Apple Push Notification: proxy"]
    section += [f"DOMAIN-SUFFIX,{domain},PROXY" for domain in config["proxy"]]
    section += [END, ""]
    block = "\n".join(section)

    marker = "[Rule]\n"
    if marker not in rules:
        raise SystemExit(f"{args.rules} has no [Rule] section")
    rules = rules.replace(marker, marker + block, 1)
    if rules.count(START) != 1 or rules.count(END) != 1:
        raise SystemExit("Personalized section was not inserted exactly once")
    for domain in config["remove_conflicting_proxy"]:
        if re.search(rf"(?im)^DOMAIN-SUFFIX,{re.escape(domain)},Proxy$", rules):
            raise SystemExit(f"Conflicting Proxy rule remains: {domain}")
    args.rules.write_text(rules, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
