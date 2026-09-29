#!/usr/bin/env bash
set -euo pipefail

deck_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
output_dir=$(realpath -m -- "${1:-$deck_dir}")
mkdir -p -- "$output_dir"

# Disposable renderer: no service sockets, credentials or network are mounted.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --tmpfs /tmp:rw,mode=1777 \
  --env XDG_CACHE_HOME=/tmp/cache --env XDG_CONFIG_HOME=/tmp/config \
  -v "$deck_dir:/input:ro" \
  -v "$deck_dir/fonts:/usr/local/share/fonts/thin-signals:ro" \
  -v "$output_dir:/output:rw" \
  --entrypoint /bin/sh \
  agi-space/pptx-export@sha256:740870472ac0495ea61d10a20da0ba891211884ac9ded835578e8fa54a5e6bf9 \
  -c 'fc-cache -f >/dev/null 2>&1; exec soffice --headless --nologo --nodefault --nolockcheck --nofirststartwizard -env:UserInstallation=file:///tmp/lo-profile --convert-to pdf:impress_pdf_Export --outdir /output /input/Thin-Signals-2026-09-29.pptx'
test -s "$output_dir/Thin-Signals-2026-09-29.pdf"
