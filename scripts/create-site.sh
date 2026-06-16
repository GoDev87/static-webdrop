#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 my-site-name" >&2
  exit 1
fi

name="$1"
case "$name" in
  *[!a-z0-9-]*|''|-*)
    echo "Invalid site name. Use lowercase letters, numbers, and hyphens only." >&2
    exit 1
    ;;
esac

mkdir -p "sites/$name"
cat > "sites/$name/index.html" <<HTML
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>$name</title>
  </head>
  <body>
    <h1>$name</h1>
    <p>This site was created by static-webdrop.</p>
  </body>
</html>
HTML

echo "Created sites/$name/index.html"
