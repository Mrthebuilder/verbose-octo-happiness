# The Gold Brick

### **Overview**
The Gold Brick is a revolutionary cryptocurrency mining device designed to empower individuals and democratize wealth creation. Partnering with a company for manufacturing, this project will redefine the global financial landscape.

---

### **Project Timeline**
#### **Phase 1: Foundation (June 27 - July 31)**
- Repository setup and roadmap creation.
- Collaboration with a company for hardware design.
- Initial software and wallet development.

#### **Phase 2: Core Development (August 1 - September 30)**
- AI integration for profitability optimization.
- User interface (UI) development and refinement.
- Comprehensive testing of prototypes.

#### **Phase 3: Polishing and Pitching (October 1 - November 11)**
- Final testing and security audits.
- Marketing and branding strategy.
- Presentation preparation for the Yahoo Financial News Desk event.

---

### **Vision**
To create the largest redistribution of wealth in history, leveling the financial playing field for the majority and empowering underserved communities.

---

### **Next Steps**
1. Hardware and software collaboration with a company. 2. AI-powered profitability modules.
3. Seamless ecosystem integration with a companies devices.

---

## Software

The `software/` package contains the profitability + AI layer:

- `software/profitability.py` — pure-math expected coins / revenue /
  electricity cost / profit / break-even price helpers. Defines the
  `Rig` and `Coin` dataclasses used across the project.
- `software/optimizer.py` — `ProfitabilityOptimizer` (scikit-learn
  backed) that ranks a slate of candidate coins by predicted daily
  profit. Falls back to the analytic formula when no model is trained.
- `software/assistant.py` — `MiningAssistant`, a natural-language Q&A
  layer on top of the optimizer with a pluggable `LLMBackend`. Ships
  with `MockBackend` (offline, deterministic), `OpenAIBackend`, and
  `AnthropicBackend`. Picks `OpenAIBackend` or `AnthropicBackend`
  automatically when `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set.
- `software/persona.py` — named assistant persona ("Brick") with hard
  refusal rules for retirement / college / borrowed-money questions.
- `software/memory.py`, `software/profile.py` — per-user conversation
  memory and profile persistence.
- `software/audit.py` — hash-chained append-only audit log so every
  recommendation can be traced back to the exact numbers it was
  based on.
- `software/integrity.py` — file-manifest hashing so tampering with
  the installed software is detectable.
- `software/portfolio.py` — pure-math dataclasses for coin holdings,
  staking yield, Treasury bonds, and IPO allocations; aggregates
  them into a single `PortfolioSummary`.
- `software/wallet.py` — read-only wallet integration. Accepts
  public addresses and caller-supplied balance snapshots and turns
  them into holdings. Brick never holds private keys.
- `software/paper.py` — paper-mode wealth projection CLI. Shows
  mining revenue plus holdings, staking, bond, and IPO projections
  with explicit disclaimers. **No wallet is connected, no funds are
  deposited, no trades are placed.**
- `software/network.py` — startup self-check that the host has no
  banned services (sshd, bluetoothd, avahi, …) and no listening
  sockets outside an explicit allowlist. Linux-oriented; skips
  gracefully on other platforms.

`mining_assistant.py` at the repo root is the standalone simulation and
now drives its numbers through `software/profitability.py` instead of
`random.uniform`.

### Paper-mode wealth projection

```bash
python -m software.paper --demo
python -m software.paper --config path/to/wealth.json
```

The CLI prints a unified projected P&L across mining revenue, coin
and stock holdings, staking yield, Treasury bonds, and IPO
allocations. Every number is a projection computed from user-supplied
inputs. See `software/paper.py` for the JSON config layout.

### Hardware target

The Brick is designed as an advisor appliance, not a miner. See
[`docs/HARDWARE_SPEC.md`](docs/HARDWARE_SPEC.md) for the reference
device (Mac mini M4), the Linux alternative (Jetson Orin Nano Super),
the outbound-only network posture, and the explicit list of what
Brick will never do (broker-dealer, money transmitter, auto-updater).

### Install & test

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

Optional extras: `pip install -e ".[openai]"` or `pip install -e ".[anthropic]"`.
