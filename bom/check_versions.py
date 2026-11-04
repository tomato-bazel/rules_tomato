"""Check that every distribution BOM version is published in a registry."""

import concurrent.futures
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


REGISTRIES = ("https://registry.tbzl.dev", "https://bcr.bazel.build")


def read_url(url):
    request = urllib.request.Request(url, headers={"User-Agent": "rules-tomato-bom-ci"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def check_version(item):
    module, version = item
    if not isinstance(module, str) or not isinstance(version, str) or not version:
        raise ValueError(f"Invalid BOM entry: {module!r} = {version!r}")
    module_path = urllib.parse.quote(module, safe="")
    version_path = urllib.parse.quote(version, safe="")
    for registry in REGISTRIES:
        prefix = f"{registry}/modules/{module_path}"
        try:
            module_file = read_url(f"{prefix}/{version_path}/MODULE.bazel")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue
            raise
        if not module_file.strip():
            raise ValueError(f"Empty MODULE.bazel: {module}@{version}")
        metadata = json.loads(read_url(f"{prefix}/metadata.json"))
        if version not in metadata.get("versions", []):
            raise ValueError(f"{module}@{version} is absent from {registry} metadata")
        source = json.loads(read_url(f"{prefix}/{version_path}/source.json"))
        if not isinstance(source, dict) or not source:
            raise ValueError(f"Invalid source.json: {module}@{version}")
        return f"{module}@{version}: {registry}"
    raise ValueError(f"Unpublished BOM version: {module}@{version}")


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("versions.json")
    document = json.loads(path.read_text())
    modules = document["modules"]
    if not isinstance(modules, dict) or not modules:
        raise ValueError("The BOM must contain a nonempty modules object")
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(check_version, item): item for item in sorted(modules.items())}
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                print(future.result(), flush=True)
            except Exception as error:
                failures.append(f"{item[0]}@{item[1]}: {error}")
    if failures:
        print("\n".join(sorted(failures)), file=sys.stderr)
        return 1
    print(f"All {len(modules)} BOM versions are published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
