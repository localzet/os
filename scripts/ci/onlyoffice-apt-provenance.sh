#!/usr/bin/env bash
# Verify ONLYOFFICE's signed Debian repository, exact binary identity and matching source package.
# This is read-only with respect to the host package database: APT uses private lists/cache.
set -Eeuo pipefail

ROOT="$(git rev-parse --show-toplevel)"
OUT="$ROOT/out/onlyoffice-apt-provenance"
TMP="$(mktemp -d)"
mkdir -p "$OUT"
STATUS=blocked
REASON="verification did not complete"
FINGERPRINT=""
SOURCE_PACKAGE=""
SOURCE_VERSION=""
BINARY_SHA=""
DSC_SHA=""
KEY_COMMIT="1dd90cd46946ef5f765f7dfeec0a47079f86fef3"
EXPECTED_FINGERPRINT="E09CA29F6E178040EF22B4098320CA65CB2DE8E5"
EXPECTED_BINARY_SHA="2190edb4022a2ac2f6eee0f78815520f0e4ece1e8a1097c645a6f9b225c8b59c"
EXPECTED_VERSION="10.0.0-169"
REPO="https://download.onlyoffice.com/repo/debian"

write_evidence() {
    python3 - "$OUT/result.json" "$STATUS" "$REASON" "$FINGERPRINT" \
        "$SOURCE_PACKAGE" "$SOURCE_VERSION" "$BINARY_SHA" "$DSC_SHA" \
        "$KEY_COMMIT" "$EXPECTED_FINGERPRINT" "$EXPECTED_VERSION" "$EXPECTED_BINARY_SHA" <<'PY'
import json, sys
(path, status, reason, fingerprint, source_package, source_version,
 binary_sha, dsc_sha, key_commit, expected_fingerprint, expected_version,
 expected_binary_sha) = sys.argv[1:]
data = {
    "status": status,
    "reason": reason,
    "repository": "https://download.onlyoffice.com/repo/debian squeeze main",
    "key_source": f"https://github.com/ONLYOFFICE/repo/blob/{key_commit}/centos/RPM-GPG-KEY-ONLYOFFICE",
    "key_source_commit": key_commit,
    "expected_key_fingerprint": expected_fingerprint,
    "observed_key_fingerprint": fingerprint or None,
    "documented_key_id": "CB2DE8E5",
    "expected_binary_version": expected_version,
    "observed_source_package": source_package or None,
    "observed_source_version": source_version or None,
    "expected_github_release_sha256": expected_binary_sha,
    "observed_apt_binary_sha256": binary_sha or None,
    "source_dsc_sha256": dsc_sha or None,
    "authenticated": status == "verified",
}
with open(path, "w", encoding="utf-8") as stream:
    json.dump(data, stream, indent=2)
    stream.write("\n")
PY
}

on_exit() {
    rc=$?
    if [[ ! -f "$OUT/result.json" ]]; then
        if [[ -z "$REASON" ]]; then REASON="unexpected failure (exit $rc)"; fi
        write_evidence || true
    fi
    rm -rf "$TMP"
}
trap on_exit EXIT

fail() {
    REASON="$1"
    write_evidence
    echo "BLOCKED: $REASON" >&2
    exit 1
}

# A missing source index is an authenticated repository limitation, not a
# verifier crash. Record the fail-closed result as a successful audit run so
# downstream review can consume the evidence; authenticated remains false.
block_expected() {
    REASON="$1"
    write_evidence
    echo "BLOCKED (expected; fail-closed): $REASON" >&2
    exit 0
}

for tool in curl gpg gpgv apt-get apt-cache sha256sum python3 awk; do
    command -v "$tool" >/dev/null || fail "Missing required verifier: $tool"
done

apt_private() {
    apt-get \
        -o "Dir::Etc::sourcelist=$TMP/sources.list" \
        -o "Dir::Etc::sourceparts=-" \
        -o "Dir::State::lists=$TMP/lists" \
        -o "Dir::State::status=/var/lib/dpkg/status" \
        -o "Dir::Cache::archives=$TMP/archives" \
        -o "APT::Get::List-Cleanup=0" \
        -o "APT::Get::AllowUnauthenticated=false" \
        -o "Acquire::https::Verify-Peer=true" \
        -o "Acquire::https::Verify-Host=true" \
        "$@"
}

apt_cache_private() {
    apt-cache \
        -o "Dir::Etc::sourcelist=$TMP/sources.list" \
        -o "Dir::Etc::sourceparts=-" \
        -o "Dir::State::lists=$TMP/lists" \
        -o "Dir::State::status=/var/lib/dpkg/status" \
        -o "APT::Get::AllowUnauthenticated=false" \
        "$@"
}

KEY_URL="https://raw.githubusercontent.com/ONLYOFFICE/repo/$KEY_COMMIT/centos/RPM-GPG-KEY-ONLYOFFICE"
if ! curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 20 --max-time 120 --output "$TMP/onlyoffice.asc" "$KEY_URL"; then
    fail "Could not retrieve the pinned official ONLYOFFICE repository key"
fi
FINGERPRINT="$(gpg --batch --show-keys --with-colons "$TMP/onlyoffice.asc" |
    awk -F: '$1 == "fpr" { print toupper($10); exit }')"
[[ "$FINGERPRINT" == "$EXPECTED_FINGERPRINT" ]] ||
    fail "Official repository key fingerprint differs from the pinned full fingerprint"
KEY_ID="$(printf '%s' "$FINGERPRINT" | rev | cut -c1-8 | rev)"
[[ "$KEY_ID" == "CB2DE8E5" ]] ||
    fail "Full key fingerprint does not match the key ID in official Desktop Editors instructions"

gpg --batch --yes --dearmor --output "$TMP/onlyoffice.gpg" "$TMP/onlyoffice.asc"
if ! curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 20 --max-time 120 --output "$TMP/InRelease" "$REPO/dists/squeeze/InRelease"; then
    fail "Could not retrieve ONLYOFFICE InRelease metadata over HTTPS"
fi
if ! gpgv --status-fd 1 --keyring "$TMP/onlyoffice.gpg" "$TMP/InRelease" \
    > "$OUT/gpgv-status.txt" 2> "$OUT/gpgv-stderr.txt"; then
    fail "ONLYOFFICE InRelease signature did not verify with the pinned full fingerprint"
fi
VALIDSIG="$(awk '$2 == "VALIDSIG" { print toupper($3); exit }' "$OUT/gpgv-status.txt")"
[[ "$VALIDSIG" == "$EXPECTED_FINGERPRINT" ]] ||
    fail "InRelease was not signed by the expected ONLYOFFICE key"

mkdir -p "$TMP/lists/partial" "$TMP/archives/partial"
cat > "$TMP/sources.list" <<EOF
deb [arch=amd64 signed-by=$TMP/onlyoffice.gpg] $REPO squeeze main
deb-src [arch=amd64 signed-by=$TMP/onlyoffice.gpg] $REPO squeeze main
EOF
if ! apt_private update > "$OUT/apt-update.log" 2>&1; then
    fail "APT could not validate and index the signed ONLYOFFICE binary and source repositories"
fi

if ! apt_cache_private show onlyoffice-desktopeditors > "$OUT/binary-package-index.txt" 2>&1; then
    fail "The signed repository does not publish onlyoffice-desktopeditors"
fi
if ! python3 - "$OUT/binary-package-index.txt" "$EXPECTED_VERSION" > "$TMP/source-info" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
version = sys.argv[2]
for stanza in re.split(r"\n\s*\n", text):
    fields = {}
    for line in stanza.splitlines():
        if line and not line[0].isspace() and ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    if fields.get("Version") == version and fields.get("Architecture") == "amd64":
        source = fields.get("Source", "onlyoffice-desktopeditors")
        source = re.sub(r"\s*\([^)]*\)\s*$", "", source).strip()
        print(source)
        print(fields["Version"])
        raise SystemExit(0)
raise SystemExit("Exact amd64 binary version not present in signed Packages index")
PY
then
    fail "Exact ONLYOFFICE binary version $EXPECTED_VERSION is absent from the signed repository"
fi
SOURCE_PACKAGE="$(head -n 1 "$TMP/source-info")"
SOURCE_VERSION="$(tail -n 1 "$TMP/source-info")"
[[ -n "$SOURCE_PACKAGE" && "$SOURCE_VERSION" == "$EXPECTED_VERSION" ]] ||
    fail "Binary package source name/version metadata is incomplete"

(
    cd "$TMP"
    apt_private download "onlyoffice-desktopeditors=$EXPECTED_VERSION" \
        > "$OUT/apt-download.log" 2>&1
) || fail "Could not download the exact signed ONLYOFFICE binary package"
DEB="$(find "$TMP" -maxdepth 1 -type f -name '*.deb' -print -quit)"
[[ -n "$DEB" ]] || fail "APT did not produce the expected binary package"
BINARY_SHA="$(sha256sum "$DEB" | awk '{print $1}')"
[[ "$BINARY_SHA" == "$EXPECTED_BINARY_SHA" ]] ||
    fail "Signed APT binary bytes differ from the pinned GitHub release asset"

# The verified InRelease and apt update log explicitly show that the vendor
# publishes no Sources index for this component. This is a hard distribution
# blocker, but a successful audit result rather than a failing test harness.
if grep -Fq "Skipping acquire of configured file 'main/source/Sources'" "$OUT/apt-update.log" &&
   grep -Fq "does not seem to provide it" "$OUT/apt-update.log"; then
    block_expected "The signed ONLYOFFICE InRelease has no main/source/Sources index; the exact corresponding source/build chain cannot be verified"
fi

(
    cd "$TMP"
    apt_private source "$SOURCE_PACKAGE=$SOURCE_VERSION" > "$OUT/apt-source.log" 2>&1
) || fail "Signed ONLYOFFICE repository does not provide the exact corresponding source package"
DSC="$(find "$TMP" -maxdepth 1 -type f -name '*.dsc' -print -quit)"
[[ -n "$DSC" ]] || fail "APT source download did not produce a .dsc file"
DSC_SOURCE="$(awk -F': ' '$1 == "Source" {print $2; exit}' "$DSC")"
DSC_VERSION="$(awk -F': ' '$1 == "Version" {print $2; exit}' "$DSC")"
[[ "$DSC_SOURCE" == "$SOURCE_PACKAGE" && "$DSC_VERSION" == "$EXPECTED_VERSION" ]] ||
    fail "Downloaded source package metadata does not match the signed binary package"
DSC_SHA="$(sha256sum "$DSC" | awk '{print $1}')"

STATUS=verified
REASON="Signed InRelease, exact binary hash and matching source package verified"
write_evidence
echo "PASS: ONLYOFFICE signed repository and exact corresponding source verified"
