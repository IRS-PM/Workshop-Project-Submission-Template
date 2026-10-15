export default function FormError({ message }: { message: string | null }) {
  if (!message) return null;

  return (
    <p
      role="alert"
      className="rounded-xl border border-accent/30 bg-accent/5 px-3.5 py-2.5 text-sm text-foreground"
    >
      {message}
    </p>
  );
}
