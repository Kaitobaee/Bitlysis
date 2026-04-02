import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bitlysis",
  description: "Phân tích dữ liệu — một click",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
        {children}
      </body>
    </html>
  );
}
