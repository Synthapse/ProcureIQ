#!/usr/bin/env python3
"""Convert .env to YAML for gcloud run deploy --env-vars-file.
Usage: python scripts/env-to-yaml.py [.env] > env.yaml
"""
import sys
import re

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ".env"
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            idx = line.find("=")
            if idx <= 0:
                continue
            key, value = line[:idx].strip(), line[idx + 1 :].strip()
            if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"')
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            value = value.replace("\\", "\\\\").replace('"', '\\"')
            print(f'{key}: "{value}"')

if __name__ == "__main__":
    main()
