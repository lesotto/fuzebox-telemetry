# fuzebox — Python SDK

The customer-facing SDK for FuzeBox AEOS. Install:

```bash
pip install fuzebox
```

Use:

```python
import fuzebox

fuzebox.init(api_key="...", tenant="acme", endpoint="https://fuzebox.acme.com")

with fuzebox.open_pel_row(skill="claims_triage", meta={"stripe_payment_intent_id": pi_id}) as row:
    result = my_agent.run(claim)
    row.set_predicted_outcome_usd(result.estimated_savings)
```

The SDK fails open: if the cosigner endpoint is unreachable, rows buffer locally
and are flushed when the connection recovers. They are tagged `unledgered`
during the buffered window.
