"use client";

type ChannelCardProps = {
  title: string;
  type?: string;
  messageCount?: number;
  flaggedCount?: number;
  riskHint?: string;
};

export function ChannelCard({
  title,
  type,
  messageCount,
  flaggedCount,
  riskHint,
}: ChannelCardProps) {
  return (
    <article className="channel-card glass-card">
      <div className="channel-card-icon" aria-hidden="true">
        ⬡
      </div>
      <div className="channel-card-body">
        <strong className="truncate">{title}</strong>
        <div className="caption">
          {[type, messageCount != null ? `${messageCount} msgs` : null, flaggedCount != null ? `${flaggedCount} flagged` : null]
            .filter(Boolean)
            .join(" · ")}
        </div>
        {riskHint ? <div className="caption channel-risk">{riskHint}</div> : null}
      </div>
    </article>
  );
}
