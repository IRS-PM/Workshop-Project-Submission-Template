import AppShell from "@/components/app-shell";
import Plate from "@/components/plate";
import PromptConsole from "@/components/prompt-console";
import CalculatorSearch from "@/components/calculator-search";
import Shortlist from "@/components/shortlist";

export default function Page() {
  return (
    <AppShell>
      <div className="flex flex-wrap items-center gap-3">
      </div>

      <div className="mt-6 grid items-center gap-6 lg:grid-cols-[minmax(0,1fr)_23rem]">
        <div>
          <h1 className="mt-3 text-[2.75rem] font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
            Less overthinking.
            <br />
            <span className="text-accent">More good food.</span>
          </h1>
        </div>

        <Plate className="mx-auto w-full max-w-sm lg:max-w-none" />
      </div>

      <div className="mt-10">
        <PromptConsole />
      </div>

      <div className="mt-6">
        <CalculatorSearch />
      </div>

      <Shortlist />
    </AppShell>
  );
}
