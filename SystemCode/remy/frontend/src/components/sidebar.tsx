"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Logo from "@/components/logo";
import { NAV } from "@/components/nav-items";

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col overflow-y-auto border-r border-subtle bg-panel px-5 py-7 lg:flex">
      <Link href="/" className="mb-9 px-1">
        <Logo />
      </Link>

      <nav className="flex flex-col gap-1">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition ${
                active
                  ? "bg-sage text-sage-foreground"
                  : "text-muted hover:bg-cream hover:text-foreground"
              }`}
            >
              <Icon className="size-5" />
              {label}
            </Link>
          );
        })}
      </nav>

      <p className="mt-auto flex items-start gap-2 px-1 text-sm leading-snug">
        <span className="mt-1.5 size-2 shrink-0 rounded-full bg-sage-deep" />
        <span>
          <span className="block text-muted">Small decisions.</span>
          <span className="block font-bold">Good days.</span>
        </span>
      </p>
    </aside>
  );
}
