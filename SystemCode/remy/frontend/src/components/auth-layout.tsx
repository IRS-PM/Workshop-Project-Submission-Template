import Link from "next/link";
import Logo from "@/components/logo";
import Plate from "@/components/plate";

/** Split screen: the brand lives on the left, the form on the right. Below lg
 *  the brand panel drops away and the form gets a compact header instead. */
export default function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh">
      <aside className="hidden w-[46%] max-w-xl flex-col justify-between border-r border-subtle bg-panel p-10 lg:flex">
        <Link href="/">
          <Logo />
        </Link>

        <div>
          <h2 className="text-5xl font-extrabold leading-[1.05] tracking-tight">
            Less overthinking.
            <br />
            <span className="text-accent">More good food.</span>
          </h2>
          <Plate className="mt-6 w-full max-w-sm" />
        </div>

        <p className="flex items-start gap-2 text-sm leading-snug">
          <span className="mt-1.5 size-2 shrink-0 rounded-full bg-sage-deep" />
          <span>
            <span className="block text-muted">Small decisions.</span>
            <span className="block font-bold">Good days.</span>
          </span>
        </p>
      </aside>

      <main className="flex flex-1 items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          <Link href="/" className="mb-8 inline-block lg:hidden">
            <Logo />
          </Link>

          <h1 className="text-3xl font-extrabold tracking-tight text-balance">
            {title}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted text-balance">
            {subtitle}
          </p>

          <div className="mt-7">{children}</div>

          <div className="mt-6 text-center text-sm text-muted">{footer}</div>
        </div>
      </main>
    </div>
  );
}
