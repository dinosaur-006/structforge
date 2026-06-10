interface ReviewData {
  improvements?: Array<{ point: string; expected_effect: string }>;
  remaining_issues?: string[];
  overall_score?: number;
  one_line_tip?: string;
}

export function AIReview({ data }: { data: unknown }) {
  if (!data) return null;
  if (typeof data === 'string') return <ReviewText text={data} />;
  if (typeof data !== 'object') return null;

  const review = data as ReviewData;
  return (
    <div className="rounded-xl border border-border bg-white px-4 py-3 shadow-sm space-y-3">
      <div className="flex items-center gap-2">
        <p className="text-sm font-semibold text-primary">AI 深度评审</p>
        {review.overall_score ? (
          <span className="font-mono text-xs font-bold text-primary">{review.overall_score}分</span>
        ) : null}
      </div>

      {review.improvements?.length ? (
        <div className="space-y-2">
          {review.improvements.map((imp, i) => (
            <div key={i} className="rounded-md border border-border-visible bg-white-hover p-2">
              <p className="text-xs font-medium text-text-primary">{imp.point}</p>
              <p className="mt-0.5 text-xs text-success">{imp.expected_effect}</p>
            </div>
          ))}
        </div>
      ) : null}

      {review.remaining_issues?.length ? (
        <div>
          <p className="text-xs font-medium text-warning">仍可改进：</p>
          {review.remaining_issues.map((issue, i) => (
            <p key={i} className="text-xs text-text-secondary">· {issue}</p>
          ))}
        </div>
      ) : null}

      {review.one_line_tip ? (
        <p className="text-xs text-text-muted italic">{review.one_line_tip}</p>
      ) : null}
    </div>
  );
}

function ReviewText({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-border bg-white px-4 py-3 shadow-sm">
      <p className="text-sm font-semibold text-primary">AI 评审意见</p>
      <p className="mt-1 text-sm leading-6 text-text-secondary">{text}</p>
    </div>
  );
}
