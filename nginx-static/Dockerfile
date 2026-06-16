FROM nginx:1.27-alpine

COPY static-sites.conf.template /etc/nginx/static-sites.conf.template
COPY docker-entrypoint.d/05-render-static-sites-config.sh /docker-entrypoint.d/05-render-static-sites-config.sh

RUN chmod +x /docker-entrypoint.d/05-render-static-sites-config.sh
