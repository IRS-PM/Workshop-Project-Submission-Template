"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Logo from "@/components/logo";
import { NAV } from "@/components/nav-items";

export default function MobileBar() {
  const pathname = usePathname();

  return (
    <header className="flex items-center justify-between border-b border-subtle bg-surface px-5 py-4 lg:hidden">
      <Link href="/">
        <Logo />
      </Link>

      {/* Icon-only on mobile: the labels live in the title/aria-label so the
          three destinations stay reachable without a drawer. */}
      <nav className="flex items-center gap-1">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              title={label}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              className={`grid size-10 place-items-center rounded-xl transition ${
                active ? "bg-sage text-sage-foreground" : "text-muted"
              }`}
            >
              <Icon className="size-5" />
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
