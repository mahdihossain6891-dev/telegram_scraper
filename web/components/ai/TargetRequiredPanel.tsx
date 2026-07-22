"use client";

type Props = {
  title: string;
  message: string;
  onSearchUsers: () => void;
  onDismiss?: () => void;
};

export function TargetRequiredPanel({
  title,
  message,
  onSearchUsers,
  onDismiss,
}: Props) {
  return (
    <section className="ai-target-gate" role="status" aria-live="polite">
      <h3>{title}</h3>
      <p>{message}</p>
      <div className="ai-target-gate-actions">
        <button type="button" className="btn primary" onClick={onSearchUsers}>
          Search Users
        </button>
        {onDismiss ? (
          <button type="button" className="btn ai-btn-ghost" onClick={onDismiss}>
            Dismiss
          </button>
        ) : null}
      </div>
    </section>
  );
}
