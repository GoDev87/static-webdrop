#!/bin/sh
set -eu

: "${SITES_BASE_DOMAIN:?SITES_BASE_DOMAIN is required, for example sites.example.com}"

# The base domain is used inside an Nginx regex. Escape dots so
# test.local becomes test\.local.
SITES_BASE_DOMAIN_REGEX=$(printf '%s' "$SITES_BASE_DOMAIN" | sed 's/\./\\./g')
export SITES_BASE_DOMAIN_REGEX

# Only substitute our generated variable. Do NOT substitute $site or $uri,
# they are Nginx variables used at request time.
envsubst '${SITES_BASE_DOMAIN_REGEX}'   < /etc/nginx/static-sites.conf.template   > /etc/nginx/conf.d/default.conf

echo "Rendered static-sites nginx config for *.${SITES_BASE_DOMAIN}"
