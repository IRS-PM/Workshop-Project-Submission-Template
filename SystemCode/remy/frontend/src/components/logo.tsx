export default function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="grid size-9 shrink-0 place-items-center rounded-[0.7rem] bg-accent">
        <svg viewBox="0 0 24 24" className="size-5" aria-hidden="true">
          {/* fork */}
          <path
            d="M8.4 4v4.2a1.6 1.6 0 0 1-3.2 0V4M6.8 4v16"
            fill="none"
            stroke="white"
            strokeWidth="1.7"
            strokeLinecap="round"
          />
          {/* spoon */}
          <path
            d="M16.4 4c1.8 0 2.8 1.6 2.8 3.6s-1 3.4-2.8 3.4-2.8-1.4-2.8-3.4S14.6 4 16.4 4Zm0 7v9"
            fill="none"
            stroke="white"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      {!compact && (
        <span className="text-[1.4rem] font-extrabold tracking-tight">
          Remy
        </span>
      )}
    </span>
  );
}
