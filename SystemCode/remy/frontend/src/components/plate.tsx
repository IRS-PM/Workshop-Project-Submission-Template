/**
 * The hero illustration: a plated meal inside a cream disc, with a sage
 * "good things coming up" stamp and a handwritten aside. Pure SVG so it stays
 * crisp at any size and costs no network request.
 */
export default function Plate({ className = "" }: { className?: string }) {
  return (
    <div className={`relative ${className}`}>
      <svg
        viewBox="0 0 400 400"
        className="w-full"
        role="img"
        aria-label="A plate of salmon, broccoli and tomatoes"
      >
        <circle cx="200" cy="200" r="168" fill="var(--cream)" />
        <circle cx="200" cy="200" r="138" fill="#fffdf8" />
        <circle cx="200" cy="200" r="138" fill="none" stroke="var(--sage-deep)" strokeWidth="2.5" />
        <circle cx="200" cy="200" r="116" fill="none" stroke="var(--sage-deep)" strokeWidth="1.5" opacity="0.5" />

        {/* salmon fillet, laid across the middle of the plate */}
        <g transform="rotate(-20 205 214)">
          <rect x="135" y="187" width="146" height="54" rx="27" fill="#e8945c" />
          <path
            d="M150 202h116M150 214h116M150 226h96"
            stroke="#f6c89c"
            strokeWidth="5"
            strokeLinecap="round"
          />
        </g>

        {/* broccoli, upper left */}
        <g transform="translate(120 112)">
          <path d="M44 58v18" stroke="#4a7a3e" strokeWidth="9" strokeLinecap="round" />
          <circle cx="30" cy="30" r="25" fill="#5f8f4e" />
          <circle cx="58" cy="38" r="21" fill="#6d9e59" />
          <circle cx="16" cy="46" r="18" fill="#537f45" />
          <circle cx="42" cy="50" r="19" fill="#6d9e59" />
        </g>

        {/* herb ring, upper right */}
        <circle cx="262" cy="144" r="17" fill="#8fb87a" />
        <circle cx="262" cy="144" r="7.5" fill="#d8e8c8" />

        {/* tomatoes */}
        <circle cx="276" cy="212" r="27" fill="#dd5b45" />
        <circle cx="267" cy="202" r="8" fill="#f09c8a" opacity="0.85" />
        <circle cx="228" cy="262" r="18" fill="#e46b52" />
        <circle cx="222" cy="256" r="5.5" fill="#f09c8a" opacity="0.85" />

        {/* orange sparkle, top right */}
        <g stroke="var(--accent)" strokeWidth="4.5" strokeLinecap="round">
          <path d="M358 52v28M344 66h28M348 56l20 20M368 56l-20 20" />
        </g>
      </svg>

      <span className="absolute bottom-[24%] left-0 grid size-[5.5rem] place-items-center rounded-full bg-sage text-center text-[0.58rem] font-bold uppercase leading-tight tracking-[0.1em] text-sage-foreground">
        Good things
        <br />
        coming up
      </span>

      <span className="absolute right-[1%] bottom-[7%] rotate-[-4deg] text-sm italic text-muted">
        a good mood, on a plate
      </span>
    </div>
  );
}
