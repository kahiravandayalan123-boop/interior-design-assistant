import { useState } from "react";
import Spinner from "./Spinner.jsx";

function initialState(questions) {
  const s = {};
  for (const q of questions) s[q.id] = q.multi ? [] : "";
  return s;
}

export default function QuestionForm({ questions, onSubmit, busy }) {
  const [values, setValues] = useState(() => initialState(questions));
  const [extra, setExtra] = useState(""); // optional free-text change request

  function setSingle(id, val) {
    setValues((v) => ({ ...v, [id]: v[id] === val ? "" : val }));
  }
  function toggleMulti(id, val) {
    setValues((v) => {
      const cur = new Set(v[id]);
      cur.has(val) ? cur.delete(val) : cur.add(val);
      return { ...v, [id]: [...cur] };
    });
  }
  function setText(id, val) {
    setValues((v) => ({ ...v, [id]: val }));
  }

  function submit(e) {
    e.preventDefault();
    const answers = questions
      .map((q) => {
        const raw = values[q.id];
        const answer = Array.isArray(raw) ? raw.join(", ") : (raw || "").trim();
        return { question_id: q.id, answer };
      })
      .filter((a) => a.answer);
    onSubmit(answers, extra.trim());
  }

  const answeredCount = questions.filter((q) => {
    const raw = values[q.id];
    return Array.isArray(raw) ? raw.length > 0 : !!(raw || "").trim();
  }).length;

  return (
    <form className="card" onSubmit={submit}>
      <h2>A few quick questions</h2>
      <p className="card-sub">
        This helps tailor the redesign to your budget and taste.
      </p>
      <p className="progress-hint">
        {answeredCount} of {questions.length} answered
      </p>

      {questions.map((q) => (
        <div className="q" key={q.id}>
          <p className="q-prompt">{q.prompt}</p>
          {q.options?.length > 0 ? (
            <div className="opts">
              {q.options.map((opt) => {
                const pressed = q.multi
                  ? values[q.id].includes(opt)
                  : values[q.id] === opt;
                return (
                  <button
                    key={opt}
                    type="button"
                    className="chip"
                    aria-pressed={pressed}
                    disabled={busy}
                    onClick={() => (q.multi ? toggleMulti(q.id, opt) : setSingle(q.id, opt))}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          ) : (
            <input
              type="text"
              value={values[q.id]}
              disabled={busy}
              onChange={(e) => setText(q.id, e.target.value)}
              placeholder="Type your answer"
            />
          )}
        </div>
      ))}

      <div className="q">
        <p className="q-prompt">
          Anything specific you'd like changed? <span className="muted">(optional)</span>
        </p>
        <textarea
          className="instruction-input"
          value={extra}
          disabled={busy}
          onChange={(e) => setExtra(e.target.value)}
          placeholder='e.g. "swap the coffee table for a round one and add a big plant by the window"'
          rows={3}
          maxLength={600}
        />
      </div>

      <div className="actions">
        <button className="primary" type="submit" disabled={busy || answeredCount === 0}>
          {busy && <Spinner />}
          {busy
            ? "Saving answers…"
            : `Submit answers (${answeredCount}/${questions.length})`}
        </button>
      </div>
    </form>
  );
}
