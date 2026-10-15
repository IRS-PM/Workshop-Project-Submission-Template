"use client";

import { Check, Close } from "@/components/icons";

type Props = {
  title: string;
  /** true liked, false not liked, undefined not rated yet. */
  like: boolean | undefined;
  saving: boolean;
  error?: string;
  onRate: (like: boolean) => void;
};

// The tick is always green and the cross always red-orange; the chosen one is filled.
const STYLES = {
  like: {
    idle: "border-[#bcd3ae] bg-[#e8f2df] text-[#3f7a34] hover:border-[#3f7a34] hover:bg-[#d6e9c7]",
    active: "border-[#3f7a34] bg-[#3f7a34] text-white",
  },
  dislike: {
    idle: "border-[#f2c1ad] bg-[#fdeee7] text-[#d4492a] hover:border-[#d4492a] hover:bg-[#fbdccf]",
    active: "border-[#d4492a] bg-[#d4492a] text-white",
  },
};

/** "Liked it" / "Not for me", after practice-project-2's RecipeLikeButtons.
 *  Each choice is added to the user's History. */
export default function LikeButtons({ title, like, saving, error, onRate }: Props) {
  const button = (value: boolean) => {
    const style = STYLES[value ? "like" : "dislike"];
    const Icon = value ? Check : Close;
    return (
      <button
        type="button"
        onClick={() => onRate(value)}
        disabled={saving}
        aria-pressed={like === value}
        aria-label={value ? `Liked ${title}` : `Did not like ${title}`}
        title={value ? "Liked it" : "Not for me"}
        className={`grid size-8 place-items-center rounded-full border transition disabled:cursor-progress disabled:opacity-60 ${
          like === value ? style.active : style.idle
        }`}
      >
        <Icon className="size-4" />
      </button>
    );
  };

  return (
    <div role="group" aria-label={`Did you like ${title}?`} aria-busy={saving} className="flex flex-wrap items-center gap-1.5">
      {button(true)}
      {button(false)}
      {error && (
        <span role="alert" className="basis-full text-xs text-[#d4492a]">
          {error}
        </span>
      )}
    </div>
  );
}
