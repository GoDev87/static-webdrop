#!/bin/sh
set -eu

: "${SITES_BASE_DOMAIN:?SITES_BASE_DOMAIN is required, for example sites.example.com}"

# Escape dots and other regex metacharacters because the value is used in a
# regex server_name. Example: sites.example.com -> sites\.example\.com
SITES_BASE_DOMAIN_REGEX=$(printf '%s' "$SITES_BASE_DOMAIN" | sed 's/[.[\*^$()+?{}|\\]/\\&/g')
export SITES_BASE_DOMAIN_REGEX

envsubst '${SITES_BASE_DOMAIN_REGEX}' \
  < /etc/nginx/static-sites.conf.template \
  > /etc/nginx/conf.d/default.conf

echo "Rendered static-sites nginx config for *.${SITES_BASE_DOMAIN}"
