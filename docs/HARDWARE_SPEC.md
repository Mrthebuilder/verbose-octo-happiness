# Brick Hardware Reference Spec

Brick is the advisor/trust layer, not the mining rig. This document
captures the hardware target the software is written against.

## Design intent

Brick is a **small, silent, desk-friendly appliance** that:

1. Runs the AI assistant ("Brick") with a local LLM so it does not
   depend on cloud reachability for its core function.
2. Runs the profitability math and the paper-mode portfolio
   projections.
3. Holds a hardware-bound keypair in a secure element — the public
   half acts like a VIN for the unit.
4. Is **outbound-only on the network**: no incoming connections, no
   Bluetooth, no discovery protocols.
5. Connects (over an encrypted outbound tunnel) to separate mining
   hardware or the user's own brokerage app — never holds user funds.

## Reference device: Apple Mac mini M4

| Attribute | Value |
|---|---|
| SoC | Apple M4 |
| CPU cores | 10 (4 P-core + 6 E-core) |
| GPU cores | 10 |
| Neural Engine | 16-core, ~38 TOPS |
| RAM | 16 GB unified (24 / 32 GB options) |
| Storage | 256 GB – 2 TB SSD |
| Power draw | ~4 W idle, ~60 W peak |
| Noise | 18–23 dBA under load (near-silent) |
| Ports | Thunderbolt 4, USB-C, HDMI, Gigabit Ethernet |
| Secure element | Apple Secure Enclave |
| MSRP | starts ~$599 |

Why this chip, not an Nvidia GPU:

* Quiet. Nvidia gaming / datacenter GPUs cannot be made quiet at any
  nontrivial load, which kills the "appliance sitting on a desk"
  product story.
* Local LLM capable. The Neural Engine + unified memory runs 7B–13B
  parameter models at interactive speed, which is exactly the scale
  Brick's persona needs.
* Secure Enclave is shipping silicon, not a datasheet promise.
* Consumer GPU mining is mostly unprofitable on electricity alone at
  2026 difficulty levels, so shipping a GPU inside Brick would give
  users net-negative returns.

Reference OS: **macOS** for day-1. A Linux variant via Asahi Linux
remains an option for users who do not want a closed-OS appliance.

## Alternative reference device: NVIDIA Jetson Orin Nano Super

For users who want a non-Apple path:

| Attribute | Value |
|---|---|
| SoC | NVIDIA Jetson Orin Nano Super |
| CPU | 6-core ARM Cortex-A78AE |
| GPU | 1024-core Ampere + 32 Tensor cores |
| AI perf | ~67 TOPS |
| RAM | 8 GB LPDDR5 |
| Storage | microSD + NVMe (user-supplied) |
| Power draw | 7–25 W |
| Noise | silent in fanless enclosure |
| MSRP | ~$249 |
| Secure element | Jetson security services (SE-OTP) |

Reference OS: **NVIDIA JetPack** (Ubuntu 22.04 base). Same software
stack as the Mac reference; only the host OS + secure-element
bindings differ.

## Mining hardware is separate

Brick never contains the miner. It talks (over an outbound-only
tunnel) to one of:

* **Bitcoin ASICs** (e.g. Bitmain Antminer S21, ~3500 W, kept in
  garage / basement) for BTC.
* **GPU rigs** the user already owns, for RVN / KAS / ALPH / ERGO.
* **Third-party pool or cloud-mining account** the user holds with a
  licensed operator.

This keeps the Brick silent and cool. It also means the Brick cannot
brick the mining hardware, and the mining hardware cannot
exfiltrate from the Brick (they are separate network zones).

## Network posture

* No listening sockets on any interface. Host firewall drops all
  incoming traffic.
* Outbound traffic restricted to a pinned allowlist (pool endpoint,
  price-feed endpoint, update-manifest endpoint).
* Bluetooth and Wi-Fi Direct disabled at the OS level.
* No mDNS / SSDP / Bonjour advertisement.
* All outbound traffic wrapped in TLS; update manifests additionally
  signed with a key whose fingerprint is shipped on the unit.

`software/network.py` performs a best-effort startup check for this
posture (banned services + listening sockets) and refuses to start
Brick if the host is misconfigured.

## Wallet / fund integration

Brick does not hold private keys. Real balances come into the paper
view via `software.wallet`, which accepts only public addresses and
caller-supplied balance snapshots. The user's own wallet app (e.g.
Unstoppable Wallet on iOS) is where keys live and transactions are
signed. Brick shows numbers; the user acts.

## Future: long-range private link (LoRa / amateur radio)

For users who want the Brick to talk to remote mining hardware
without routing over public Wi-Fi, two paths are under
consideration — **not implemented yet**:

* **LoRa** (868 MHz EU / 915 MHz US) — license-free ISM band, ~10 km
  line-of-sight, kilobit data rates, plenty for signed control
  messages. Plug-in USB module such as the Heltec WiFi LoRa 32.
* **Licensed amateur radio data modes** — multi-km range at higher
  data rates, requires a Technician-class (or equivalent) license.

Both require encryption at the application layer; RF alone provides
no security. Both are additive to, not replacements for, the
standard outbound-only Wi-Fi / Ethernet path. These are tracked in
the roadmap and not shipped today.

## What Brick will never be

Written down explicitly so scope creep cannot quietly flip these
over:

* Not a broker-dealer. Cannot execute trades on the user's behalf.
* Not a money transmitter. Cannot hold, move, or custody user funds.
* Not unhackable. Every line of code, every firmware chip, and every
  network tunnel has a threat model, not a guarantee.
* Not an auto-update-every-second daemon. Updates are signed,
  user-initiated, and infrequent.
