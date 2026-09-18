import type { Metadata } from "next";
import "./globals.css";
import { DashboardLayout } from "@/components/layout/DashboardLayout";

export const metadata: Metadata = {
  title: "TikTok Manager | Operations Dashboard",
  description: "Scalable platform for legitimate TikTok account and content operations",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-50 text-slate-900 font-sans">
        <DashboardLayout>{children}</DashboardLayout>
      </body>
    </html>
  );
}
