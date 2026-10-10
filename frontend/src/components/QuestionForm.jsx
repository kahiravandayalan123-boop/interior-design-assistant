import { useState } from "react";
import Spinner from "./Spinner.jsx";

// Preferences step: a fixed set of single-choice questions. One answer per
// question; optional ones are marked and can be skipped.
export default function QuestionForm({ questions, onSubmit, busy }) {
  const [values, setValues] = useState({});
  const [extra, setExtra] = useState(""); // optional free-text change request

  function choose(id, val) {
    setValues((v) => ({ ...v, [id]: v[id] === val ? "" : val }));
  }

  const missing = questions.filter((q) => !q.optional && !values[q.id]);

  function submit(e) {
    e.preventDefault();
    if (missing.length) return;
    const answers = questions
      .filter((q) => values[q.id])
      .map((q) => ({ question_id: q.id, answer: values[q.id] }));
    onSubmit(answers, extra.trim());
  }

  return (
    <form className="card" onSubmit={submit}>
      <p className="eyebrow">Step 2 · Preferences</p>
      <h2>A few quick questions</h2>
      <p className="card-sub">This helps tailor the redesign to your budget and taste. Pick one option per question.</p>

      {questions.map((q, i) => (
        <div className="q" key={q.id} role="group" aria-label={q.prompt}>
          <p className="q-prompt">
            <span className="q-num">{i + 1}</span>
            {q.prompt}
            {q.optional && <span className="q-optional">Optional</span>}
          </p>
          {q.hint && <p className="q-hint">{q.hint}</p>}
          <div className="opts">
            {q.options.map((opt) => (
              <button
                key={opt}
                type="button"
                className="chip"
                aria-pressed={values[q.id] === opt}
                disabled={busy}
                onClick={() => choose(q.id, opt)}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ))}

      <div className="q">
        <p className="q-prompt">
          <span className="q-num">{questions.length + 1}</span>
          Anything specific you'd like changed?
          <span className="q-optional">Optional</span>
        </p>
        <textarea
          className="instruction-input"
          value={extra}
          disabled={busy}
          onChange={(e) => setExtra(e.target.value)}
          placeholder="e.g. keep my armchair, and add a tall plant by the window"
          rows={2}
          maxLength={600}
        />
      </div>

      <div className="actions">
        <button className="primary" type="submit" disabled={busy || missing.length > 0}>
          {busy && <Spinner />}
          {busy ? "Saving…" : "Generate my redesign"}
        </button>
        {missing.length > 0 && (
          <span className="actions-note">
            {missing.length} question{missing.length > 1 ? "s" : ""} left
          </span>
        )}
      </div>
    </form>
  );
}
