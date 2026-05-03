# Customer Integration — 5 steps

This is what a customer engineer does to get their agent into FuzeBox AEOS.
The path is the same on every platform.

1. **Install the SDK.**
   ```bash
   pip install fuzebox          # Python
   npm install @fuzebox/sdk     # Node (Sprint 4)
   ```

2. **Initialize once, at process start.**
   ```python
   import fuzebox
   fuzebox.init(api_key=os.environ["FUZEBOX_API_KEY"],
                tenant="acme",
                endpoint="https://fuzebox.acme.internal")
   ```

3. **Wrap each agent execution in `open_pel_row`.**
   ```python
   with fuzebox.open_pel_row(skill="claims_triage",
                             meta={"stripe_payment_intent_id": pi_id}) as row:
       result = my_agent.run(claim)
       row.set_predicted_outcome_usd(result.estimated_savings)
   ```

4. **Tag the cosign match key in `meta`.** Stripe uses
   `stripe_payment_intent_id`; Salesforce uses `salesforce_opportunity_id`.

5. **(Optional) ship LLM call costs.** LiteLLM auto-instrumentation lands in
   Sprint 2 — until then, pass `cost_usd=` explicitly.

You can deploy your agent immediately. The SDK fails open: if the FuzeBox
cosigner is unreachable, rows buffer locally and reconcile later. The agent
is never blocked.
