import { Clock } from "@/components/icons";

// Placeholder rows until the recommender is wired up. The two colours drive the
// card's gradient so each tile reads as a distinct dish without an image file.
const IDEAS = [
  { name: "Miso butter salmon", minutes: 20, tags: ["High protein", "Japanese"], from: "#f3c39a", to: "#e8945c" },
  { name: "Charred broccoli rice bowl", minutes: 25, tags: ["Vegetarian", "Korean"], from: "#c9dfb8", to: "#6d9e59" },
  { name: "Tomato & chickpea stew", minutes: 30, tags: ["Halal", "Middle Eastern"], from: "#f0a894", to: "#dd5b45" },
  { name: "Lemongrass chicken noodles", minutes: 22, tags: ["High protein", "Vietnamese"], from: "#f6dda3", to: "#d9a83f" },
  { name: "Coconut dhal", minutes: 28, tags: ["Vegetarian", "Indian"], from: "#f7e2b0", to: "#e2b35c" },
  { name: "Sambal green beans & egg", minutes: 18, tags: ["Halal", "Malay"], from: "#cfe0c2", to: "#7fa96a" },
];

export default function Shortlist() {
  return (
    <section className="mt-14">
      <p className="eyebrow">A little inspiration</p>
      <h2 className="mt-2 text-3xl font-extrabold tracking-tight">
        Your shortlist
      </h2>

      <ul className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {IDEAS.map((idea) => (
          <li
            key={idea.name}
            className="group overflow-hidden rounded-2xl border border-subtle bg-surface transition hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-14px_rgba(33,56,42,0.25)]"
          >
            <div
              className="h-28"
              style={{
                background: `linear-gradient(135deg, ${idea.from}, ${idea.to})`,
              }}
            />
            <div className="p-4">
              <h3 className="font-bold leading-snug">{idea.name}</h3>
              <p className="mt-1.5 flex items-center gap-1.5 text-sm text-muted">
                <Clock className="size-4" />
                {idea.minutes} min
              </p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {idea.tags.map((tag) => (
                  <li
                    key={tag}
                    className="rounded-full bg-cream px-2.5 py-1 text-xs font-medium text-muted"
                  >
                    {tag}
                  </li>
                ))}
              </ul>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
