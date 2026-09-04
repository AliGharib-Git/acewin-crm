# Ubuntu production deployment

## Prerequisites

- Ubuntu 22.04+ server with a public IPv4 address.
- A DNS `A` record for `acewin-group.top` points to that address. Do not
  proceed with Let's Encrypt until propagation is visible.
- TCP ports 80 and 443 are allowed in the cloud firewall and UFW. SSH remains
  restricted to the administrator's IP where possible.
- Docker Engine with the Docker Compose plugin, Nginx, Certbot, and the Nginx
  Certbot plugin are installed.

## First release

```bash
sudo mkdir -p /opt/acewin-crm /var/www/certbot
sudo chown "$USER":"$USER" /opt/acewin-crm
git clone <repository-url> /opt/acewin-crm
cd /opt/acewin-crm
cp deploy/env.production.example .env
chmod 600 .env
# Set POSTGRES_PASSWORD and SECRET_KEY to unique random values in .env.
docker compose up -d --build
```

Install `deploy/nginx/acewin-group.top.bootstrap.conf` as
`/etc/nginx/sites-available/acewin-group.top.conf`, enable it, and validate:

```bash
sudo ln -s /etc/nginx/sites-available/acewin-group.top.conf /etc/nginx/sites-enabled/acewin-group.top.conf
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/certbot -d acewin-group.top
```

Replace the bootstrap config with `deploy/nginx/acewin-group.top.conf`, then:

```bash
sudo nginx -t && sudo systemctl reload nginx
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo systemctl enable --now certbot.timer
./deploy/server-verify.sh acewin-group.top
```

## Future releases

```bash
cd /opt/acewin-crm
git pull --ff-only
docker compose up -d --build --remove-orphans
./deploy/server-verify.sh acewin-group.top
```

The Postgres volume (`pgdata`) is persistent. Do not run `docker compose down
-v` in production: it deletes the database volume.
