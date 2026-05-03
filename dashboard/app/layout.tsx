import type { ReactNode } from 'react';

export const metadata = { title: 'FuzeBox AEOS' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header style={{ padding: '1rem', borderBottom: '1px solid #eee' }}>
          <strong>FuzeBox AEOS</strong>
          <nav style={{ marginLeft: '1rem' }}>
            <a href="/overview">Overview</a> ·{' '}
            <a href="/agents">Agents</a> ·{' '}
            <a href="/skills">Skills</a> ·{' '}
            <a href="/anomalies">Anomalies</a> ·{' '}
            <a href="/trust">Trust</a> ·{' '}
            <a href="/infra">Infra</a>
          </nav>
        </header>
        <main style={{ padding: '1rem' }}>{children}</main>
      </body>
    </html>
  );
}
