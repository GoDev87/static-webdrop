# static-webdrop

Drop folders containing static HTML websites into `./sites`, and serve each one as a subdomain behind Nginx Proxy Manager.

Example:

```text
./sites/hello/index.html -> https://hello.sites.example.com
./sites/docs/index.html  -> https://docs.sites.example.com
```

The watcher can also create/update Homarr Apps for each folder.

## What this stack does

- `static-sites`: Nginx container serving `/sites/<folder>` based on the requested subdomain.
- `site-watcher`: Python container scanning folders and optionally syncing Homarr Apps.
- Nginx Proxy Manager: you create **one wildcard proxy host** manually.
- DNS: you create **one wildcard DNS record** manually.

It intentionally avoids creating one NPM host per folder. One wildcard NPM host is simpler and more reliable.

## Requirements

- Docker + Docker Compose
- Existing Nginx Proxy Manager
- Existing Homarr, optional but recommended
- A domain or local DNS zone where you can create a wildcard record

## Setup

### 1. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Important values:

```env
SITES_BASE_DOMAIN=sites.example.com
NPM_NETWORK=nginxproxymanager_default
HOST_SITES_DIR=./sites
```

Find the NPM Docker network with:

```bash
docker network ls
```

If your NPM compose project is called `nginxproxymanager`, the network is often `nginxproxymanager_default`.

### 2. Create the external Docker network if needed

If you do not already have an NPM network, create one and attach both NPM and this stack to it:

```bash
docker network create npm
```

Then set:

```env
NPM_NETWORK=npm
```

### 3. Start the stack

```bash
docker compose up -d --build
```

Check logs:

```bash
docker compose logs -f static-sites site-watcher
```

## Nginx Proxy Manager configuration

Create one proxy host:

```text
Domain Names: *.sites.example.com
Scheme: http
Forward Hostname / IP: static-sites
Forward Port: 8080
Websockets Support: disabled
```

SSL tab:

```text
SSL Certificate: your wildcard certificate for *.sites.example.com
Force SSL: enabled
HTTP/2 Support: enabled
```

For a real public wildcard certificate, use a DNS challenge in NPM.

## DNS configuration

Create a wildcard DNS record:

```text
*.sites.example.com -> your NPM server IP
```

For a local-only homelab, do this in Pi-hole, AdGuard Home, Technitium, your router, or your local DNS server.

## Homarr sync

Homarr sync is optional.

Create a Homarr API key:

```text
Homarr -> Management -> Tools -> API -> Authentication
```

Then edit `.env`:

```env
HOMARR_ENABLED=1
HOMARR_URL=http://homarr:7575
HOMARR_API_KEY=<id>.<token>
```

The watcher creates/updates Homarr Apps using:

```text
GET    /api/apps
POST   /api/apps
PATCH  /api/apps/{id}
DELETE /api/apps/{id}   only if DELETE_REMOVED=1
```

Note: depending on your Homarr version/layout, API-created Apps may still need to be placed on a board manually. Homarr currently exposes Apps through the API; full board placement automation may depend on your version.

## Add a site

Manual:

```bash
mkdir -p sites/my-site
cat > sites/my-site/index.html <<'HTML'
<!doctype html>
<html><body><h1>Hello</h1></body></html>
HTML
```

Or use the helper:

```bash
./scripts/create-site.sh my-site
```

Then open:

```text
https://my-site.sites.example.com
```

## Naming rules

Folder names must match:

```text
lowercase letters, numbers, and hyphens only
```

Valid:

```text
hello
my-docs
site123
```

Invalid:

```text
MySite
site_name
site.example
```

## Test without NPM

The compose file exposes Nginx on localhost by default:

```env
STATIC_HTTP_PORT=127.0.0.1:18080
```

Add a temporary `/etc/hosts` entry:

```text
127.0.0.1 hello.sites.example.com
```

Then test:

```bash
curl -H 'Host: hello.sites.example.com' http://127.0.0.1:18080/
```

## Troubleshooting

### NPM cannot reach `static-sites`

Make sure this stack and NPM are on the same Docker network.

```bash
docker network inspect nginxproxymanager_default
```

You should see both the NPM container and `static-sites`.

### Homarr says unauthorized

Make sure the key is in the format:

```text
<id>.<token>
```

Keep:

```env
HOMARR_AUTH_MODE=apikey
```

If your installation expects bearer auth, try:

```env
HOMARR_AUTH_MODE=bearer
```

or:

```env
HOMARR_AUTH_MODE=both
```

### Site returns 404

Check that the folder has an `index.html`:

```text
sites/my-site/index.html
```

and that the hostname is:

```text
my-site.sites.example.com
```

