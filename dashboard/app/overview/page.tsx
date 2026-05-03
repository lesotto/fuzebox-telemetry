/**
 * Overview — Return on Process (RoP) and Cost per Unit of Work (CUoW) cards.
 * Pulls aggregates from the cosigner API; in Sprint 4 we only render structure.
 */

async function getSummary() {
  // Server component fetch. In production this hits the customer's cosigner.
  const url = `${process.env.COSIGNER_URL}/v1/dashboard/overview`;
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch {
    return { rop: null, cuow: null };
  }
}

export default async function Overview() {
  const data = await getSummary();
  return (
    <div>
      <h1>Overview</h1>
      <div style={{ display: 'flex', gap: '2rem', marginTop: '1rem' }}>
        <Card title="Return on Process (RoP)" value={data.rop ?? '—'} />
        <Card title="Cost per Unit of Work" value={data.cuow ?? '—'} />
      </div>
      <p style={{ marginTop: '2rem', color: '#666' }}>
        Sprint 4 ships the structure; Sprint 5 wires the live aggregates from the cosigner.
      </p>
    </div>
  );
}

function Card({ title, value }: { title: string; value: string | number }) {
  return (
    <div style={{ border: '1px solid #ddd', padding: '1rem', borderRadius: 6 }}>
      <div style={{ color: '#666', fontSize: 12 }}>{title}</div>
      <div style={{ fontSize: 28, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
