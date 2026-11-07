# Halo Relay

The signaling service for **Halo Remote** (remote desktop for Halo OS — design in `docs/REMOTE_DESKTOP.md`).
Your Halo PC and your paired phone/tablet/Chromebook dial *out* to it, so nothing on your PC listens on the
internet. It only introduces devices to each other:

- **Login** — each device answers a one-time challenge with its SAINT Link key. No passwords, no accounts to
  create: an "account" is one PC (the SHA-256 of its public key).
- **Presence** — which of your PCs are online.
- **Routing** — passes `session.*`, `sdp.*`, `ice` and `pair.*` messages, and only between a PC and a device
  that PC has allowed (the PC sends the list; remove a device in SAINT → Devices and its route is gone at once).
  Session messages are signed with keys the relay doesn't have, so it can't forge or alter them.
- **TURN credentials** — short-lived (12 h) credentials for the coturn next to it, used only when the two
  devices can't reach each other directly. Media is encrypted end to end (DTLS-SRTP) either way.
- **The browser client** — serves `web/remote/` at `/`.

State is in memory; after a restart PCs reconnect within seconds and resend their device lists.

## Run it locally (development)

```bash
pip install -r server/relay/requirements.txt
python -m server.relay.relay --port 8080        # from the repository root
```

Open `http://localhost:8080/` (browsers allow WebCrypto on `localhost` without HTTPS). Tests:
`python -m pytest tests/test_relay.py` — they start the relay on a local port and use real WebSockets.

## Host it (one small VPS)

1. A VPS with a public IPv4 address, Docker and Docker Compose. Point a DNS name at it
   (`relay.example.com`).
2. Open TCP 80, 443 (HTTPS + WSS), TCP/UDP 3478 (STUN/TURN), TCP 5349 (TURN over TLS, optional) and
   UDP 49160–49200 (TURN media) in its firewall.
3. In this folder:
   ```bash
   cp relay.env.example .env        # set HALO_DOMAIN, HALO_PUBLIC_IP, HALO_TURN_SECRET (openssl rand -hex 32)
   docker compose up -d
   ```
   Caddy gets a Let's Encrypt certificate automatically. For `turns:` on 5349 put a certificate for the same
   name in `turn-certs/<domain>.crt` / `.key` (e.g. copy Caddy's); without it TURN still works on 3478.
4. On the PC: SAINT → Devices → Remote access → relay `wss://relay.example.com/ws`
   (or `halo-remote set-relay wss://relay.example.com/ws`).

`.env` is git-ignored — never commit the TURN secret.

Check it: `curl https://relay.example.com/healthz` answers `{"ok": true, ...}` (`online` counts connected devices), and on the
PC `journalctl --user -u halo-remote` logs `remote.online relay=wss://…`. TURN: open `https://relay.example.com/` on a phone **on cellular** and connect — the
stats line says `via TURN` when the relay carried the media.

## Host it without Docker (systemd)

For a VPS where you'd rather not run Docker (Debian/Ubuntu/Arch commands are the same apart from the package
manager). The relay is plain Python + aiohttp; coturn and Caddy come from the distribution.

```bash
# 1. the relay
sudo useradd --system --home /opt/halo-relay --shell /usr/sbin/nologin halo-relay
sudo git clone https://github.com/uberdiz/Halo.git /opt/halo-relay
sudo python3 -m venv /opt/halo-relay/.venv
sudo /opt/halo-relay/.venv/bin/pip install -r /opt/halo-relay/server/relay/requirements.txt
SECRET=$(openssl rand -hex 32)
sudo tee /etc/halo-relay.env >/dev/null <<EOF
HALO_STUN_URLS=stun:relay.example.com:3478
HALO_TURN_URLS=turn:relay.example.com:3478?transport=udp,turn:relay.example.com:3478?transport=tcp,turns:relay.example.com:5349?transport=tcp
HALO_TURN_SECRET=$SECRET
EOF
sudo chmod 600 /etc/halo-relay.env
sudo cp /opt/halo-relay/server/relay/halo-relay.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now halo-relay

# 2. TURN (coturn) — the same secret
sudo apt install coturn            # or: pacman -S coturn / dnf install coturn
sudo tee /etc/turnserver.conf >/dev/null <<EOF
listening-port=3478
tls-listening-port=5349
fingerprint
use-auth-secret
static-auth-secret=$SECRET
realm=relay.example.com
external-ip=203.0.113.10
min-port=49160
max-port=49200
no-cli
no-multicast-peers
denied-peer-ip=10.0.0.0-10.255.255.255
denied-peer-ip=172.16.0.0-172.31.255.255
denied-peer-ip=192.168.0.0-192.168.255.255
denied-peer-ip=127.0.0.0-127.255.255.255
# for turns: on 5349 (optional): a certificate for the same name
# cert=/etc/letsencrypt/live/relay.example.com/fullchain.pem
# pkey=/etc/letsencrypt/live/relay.example.com/privkey.pem
EOF
sudo systemctl enable --now coturn

# 3. HTTPS + WSS in front (Caddy gets the certificate by itself)
sudo apt install caddy
sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
relay.example.com {
	encode gzip
	reverse_proxy 127.0.0.1:8080
}
EOF
sudo systemctl reload caddy
```

Same firewall ports as above. Update with `cd /opt/halo-relay && sudo git pull && sudo systemctl restart halo-relay`
(PCs and phones reconnect by themselves within seconds). Logs: `journalctl -u halo-relay -f`.

## TURN fallback: when it's used

Clients and the PC try, in order: a direct connection on the same network, a direct connection through each side's
NAT (STUN), and only then TURN through coturn (UDP 3478, then TCP 3478, then TLS 5349 for networks that block
everything else). The relay hands out TURN credentials that expire after 12 h, derived from `HALO_TURN_SECRET`
(coturn's `use-auth-secret`), so no TURN passwords are stored anywhere. Without `HALO_TURN_SECRET` the relay
only offers STUN: sessions between two strict NATs (many cellular networks) then fail with "Couldn't reach the PC".

## What it costs

| | Typical | Notes |
|---|---|---|
| VPS (1 vCPU, 1 GB RAM) | about **$4–6 / month** (Hetzner CX22, DigitalOcean/Vultr basic droplet) | Signaling is tiny: thousands of devices fit on this |
| Traffic | usually included (Hetzner: 20 TB/month) | Only TURN-relayed sessions use the VPS's bandwidth |
| TURN usage | **~2–4 GB per relayed hour** at 1080p/30 fps (4–8 Mbit/s), ~1 GB at 720p | Most sessions go peer-to-peer; TURN is the fallback for strict NAT/cellular CGNAT (roughly 10–20 % of sessions) |
| Domain | ~$10 / year | Any name you control; a free DuckDNS subdomain works too |

Prices are indicative (late 2026); check the provider. A free-tier ARM VM (e.g. Oracle Cloud) runs it too.
If all your devices are on Tailscale you can skip the relay's TURN entirely: Tailscale already connects them.

## Security notes

- The relay never sees private keys, screen contents, keystrokes or files.
- A login must finish within 10 s and each connection is capped at 200 messages a second; pairing requests are limited to 5 per minute per
  address, and the PC cancels a pairing code after repeated wrong guesses.
- A compromised relay can deny service or learn *which* devices talk to which PC and when; it cannot see or
  control your screen.
