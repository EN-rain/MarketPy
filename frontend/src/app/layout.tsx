import type { Metadata } from 'next';
import './globals.css';
import TerminalShell from '@/terminal/components/TerminalShell';

export const metadata: Metadata = {
  title: 'MarketPy Terminal',
  description: 'Terminal UI frontend for MarketPy.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <TerminalShell>{children}</TerminalShell>
      </body>
    </html>
  );
}
