"use client";

/** The pill used for every multi- and single-select choice in the app. */
export default function Chip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`rounded-full border px-3.5 py-1.5 text-sm transition ${
        selected
          ? "border-sage-deep bg-sage font-medium text-sage-foreground"
          : "border-subtle text-muted hover:border-sage-deep hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
}
