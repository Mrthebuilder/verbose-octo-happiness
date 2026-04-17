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

`mining_assistant.py` at the repo root is the standalone simulation and
now drives its numbers through `software/profitability.py` instead of
`random.uniform`.

### Install & test

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

Optional extras: `pip install -e ".[openai]"` or `pip install -e ".[anthropic]"`.
