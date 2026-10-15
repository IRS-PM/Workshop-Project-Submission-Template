"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bubble, Sparkle } from "@/components/icons";
import LikeButtons from "@/components/like-buttons";
import MealDialog from "@/components/meal-dialog";
import { MealCard } from "@/components/plan-view";
import { loadPreferences } from "@/lib/api";
import { generatePlan, type PlanMeal } from "@/lib/plan-api";
import {
  NO_CONSTRAINTS,
  fromPreferences,
  ideaRequest,
  mergeConstraints,
  readPrompt,
  replyFor,
  uniqueIdeas,
  type Constraints,
} from "@/lib/prompt-ideas";
import { useRatings } from "@/lib/use-ratings";
import { useSavedMeals } from "@/lib/use-saved-meals";

const STARTERS = ["Something light", "Plant-powered", "Protein please", "Surprise me"];
const REFINEMENTS = ["Make it filling", "No dairy", "More protein"];

type Reply = {
  id: number;
  from: "remy";
  text: string;
  note?: string;
  ideas?: PlanMeal[];
  pending?: boolean;
  failed?: boolean;
  unverified?: boolean;
};

type Message = { id: number; from: "you"; text: string } | Reply;

export default function PromptConsole() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState(false);
  const [preferences, setPreferences] = useState<Constraints>(NO_CONSTRAINTS);
  const [constraints, setConstraints] = useState<Constraints | null>(null);
  const [open, setOpen] = useState<{ meal: PlanMeal; label: string } | null>(null);
  const saved = useSavedMeals();
  const ratings = useRatings();

  const likeButtons = (meal: PlanMeal) => (
    <LikeButtons
      title={meal.title}
      like={ratings.likeOf(meal.recipe_id)}
      saving={ratings.busy === meal.recipe_id}
      error={ratings.errors[meal.recipe_id]}
      onRate={(like) => void ratings.rate(meal, like)}
    />
  );
  const nextId = useRef(0);
  const trimmed = draft.trim();

  useEffect(() => {
    let cancelled = false;
    loadPreferences()
      .then((stored) => {
        if (!cancelled) setPreferences(fromPreferences(stored));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  function updateReply(id: number, patch: Partial<Reply>) {
    setMessages((current) =>
      current.map((message) => (message.id === id && message.from === "remy" ? { ...message, ...patch } : message)),
    );
  }

  async function send(text: string) {
    const value = text.trim();
    if (!value || pending) return;

    const reading = readPrompt(value);
    const next = mergeConstraints(reading.reset || !constraints ? preferences : constraints, reading.found);
    const askId = nextId.current++;
    const replyId = nextId.current++;

    setConstraints(next);
    setMessages((current) => [
      ...current,
      { id: askId, from: "you", text: value },
      { id: replyId, from: "remy", text: "Looking for ideas…", pending: true },
    ]);
    setDraft("");
    setPending(true);

    try {
      const plan = await generatePlan(ideaRequest(next), {
        onProgress: (progress) => updateReply(replyId, { text: `${progress.message}…` }),
      });
      const ideas = uniqueIdeas(plan);
      const unverified = Object.values(plan.validation_summary).includes("unverified");
      updateReply(replyId, {
        ...replyFor(ideas, next, reading), ideas, pending: false, unverified,
        ...(unverified ? { text: "Here are screened ideas; your allergy/dietary restrictions are unverified." } : {}),
      });
    } catch (caught) {
      updateReply(replyId, {
        text: caught instanceof Error ? caught.message : "I couldn't fetch ideas just now. Please try again.",
        pending: false,
        failed: true,
      });
    } finally {
      setPending(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(draft);
    }
  }

  const canSend = trimmed !== "" && !pending;

  return (
    <section>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void send(draft);
        }}
        className="rounded-3xl border border-subtle bg-surface p-5 shadow-[0_1px_2px_rgba(33,56,42,0.04),0_12px_32px_-12px_rgba(33,56,42,0.12)] sm:p-6"
      >
        <p className="mb-3 flex items-center gap-2 text-sm font-bold">
          <Sparkle className="size-[1.15rem] text-accent" />
          Tell me what sounds good
        </p>

        <div className="flex items-start gap-3">
          <label htmlFor="prompt" className="sr-only">
            What sounds good?
          </label>
          <textarea
            id="prompt"
            rows={2}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Something filling and high in protein, no dairy…"
            className="min-w-0 flex-1 resize-none bg-transparent text-lg leading-relaxed outline-none placeholder:text-muted/70 sm:text-xl"
          />

          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send"
            className={`grid size-11 shrink-0 place-items-center rounded-full transition ${
              canSend
                ? "bg-accent text-accent-foreground hover:opacity-90"
                : "bg-cream text-muted/50"
            }`}
          >
            <ArrowUp className="size-5" />
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {STARTERS.map((starter) => (
            <button
              key={starter}
              type="button"
              disabled={pending}
              onClick={() => void send(starter)}
              className="rounded-full border border-subtle px-3.5 py-1.5 text-sm text-muted transition hover:border-sage-deep hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              {starter}
            </button>
          ))}
        </div>
      </form>

      {messages.length > 0 && (
        <>
          <div className="mt-8 space-y-3" aria-live="polite">
            {messages.map((message) =>
              message.from === "you" ? (
                <p
                  key={message.id}
                  className="ml-auto w-fit max-w-[80%] rounded-2xl bg-sage px-4 py-2.5 text-sm text-sage-foreground"
                >
                  {message.text}
                </p>
              ) : (
                <div key={message.id} aria-busy={message.pending}>
                  <p
                    className={`flex w-fit max-w-[85%] items-center gap-2.5 rounded-2xl border bg-surface px-4 py-2.5 text-sm ${
                      message.failed ? "border-accent/40" : "border-subtle"
                    } ${message.pending ? "animate-pulse" : ""}`}
                  >
                    <Bubble className="size-[1.15rem] shrink-0 text-muted" />
                    {message.text}
                  </p>
                  {message.note && <p className="mt-1.5 pl-1 text-xs text-muted">{message.note}</p>}
                  {message.unverified && (
                    <p role="alert" className="mt-3 rounded-2xl border border-accent bg-accent/10 p-4 text-sm font-semibold">
                      Known conflicts were screened out, but missing evidence is not proof of safety.
                      These ideas are not guaranteed allergy-safe or diet-compliant; check every ingredient and product label.
                    </p>
                  )}
                  {message.ideas && message.ideas.length > 0 && (
                    <ul className="mt-3 grid gap-3 sm:grid-cols-3">
                      {message.ideas.map((meal, index) => (
                        <MealCard
                          key={meal.recipe_id}
                          meal={meal}
                          label={`Idea ${index + 1}`}
                          saved={saved.isSaved(meal.recipe_id)}
                          onOpen={() => setOpen({ meal, label: `Idea ${index + 1}` })}
                          footer={likeButtons(meal)}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              ),
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted">Refine it</span>
            {REFINEMENTS.map((refinement) => (
              <button
                key={refinement}
                type="button"
                disabled={pending}
                onClick={() => void send(refinement)}
                className="rounded-full bg-sage px-3.5 py-1.5 text-sm font-medium text-sage-foreground transition hover:bg-sage-deep disabled:cursor-not-allowed disabled:opacity-50"
              >
                {refinement}
              </button>
            ))}
          </div>
        </>
      )}

      <MealDialog
        meal={open?.meal ?? null}
        label={open?.label}
        saved={open ? saved.isSaved(open.meal.recipe_id) : false}
        saving={open !== null && saved.busy === open.meal.recipe_id}
        error={open ? saved.error : null}
        onToggleSave={() => open && void saved.toggle(open.meal)}
        onClose={() => setOpen(null)}
        rating={open && likeButtons(open.meal)}
      />
    </section>
  );
}
