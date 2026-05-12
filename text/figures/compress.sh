#!/usr/bin/env bash
set -euo pipefail

for file in \
    admin_panel.jpg \
    three_devices_setup.jpg \
    wide_setup.jpg \
    windows_participation.jpg
do
    out="compressed_${file}"

    magick "$file" \
        -resize '1800x1800>' \
        -strip \
        -sampling-factor 4:2:0 \
        -quality 82 \
        "$out"

    echo "$file -> $out"
    ls -lh "$out"
done
