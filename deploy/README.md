# Live URL

Runs on the builder's own server behind Traefik, the same way its other demos run. No secret is in this folder: the service reads MODEL_API_KEY from an env file outside the repo.

1. DNS: an A record `frontdesk.aaroncabantugan.com` to the server's public IP.
2. Service: `cp deploy/frontdesk.service /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now frontdesk`
3. Route: `cp deploy/frontdesk.yml /docker/traefik/dynamic/` (Traefik watches the folder and gets the certificate on the first request).
4. Check: `curl -s https://frontdesk.aaroncabantugan.com/ | head -c 200`
