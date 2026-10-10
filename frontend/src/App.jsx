import { useEffect, useState } from "react";
import {
  ApiError,
  getConfig,
  uploadRoom,
  sendAnswers,
  generateRedesign,
  modifyRoom,
} from "./api.js";
import LandingScreen from "./components/LandingScreen.jsx";
import UploadStep from "./components/UploadStep.jsx";
import ModifyStep from "./components/ModifyStep.jsx";
import AnalysisCard from "./components/AnalysisCard.jsx";
import QuestionForm from "./components/QuestionForm.jsx";
import ResultView from "./components/ResultView.jsx";
import Stepper from "./components/Stepper.jsx";
import Alert from "./components/Alert.jsx";
import { ProgressPanel } from "./components/Spinner.jsx";

// Estimated step timings for the progress panels (seconds from request start).
const ANALYZE_STEPS = [
  { label: "Uploading your photo", at: 0 },
  { label: "Mapping windows, doors and room size", at: 2 },
  { label: "Judging each piece of furniture against the room", at: 10 },
];
const GENERATE_STEPS = [
  { label: "Planning what to keep, replace and add", at: 0 },
  { label: "Rendering the redesign onto your photo", at: 15 },
  { label: "Checking the architecture against your photo", at: 55 },
  { label: "Building your shopping list", at: 75 },
];
const MODIFY_STEPS = [
  { label: "Assessing your room and furniture", at: 0 },
  { label: "Planning your requested change", at: 20 },
  { label: "Rendering the redesign onto your photo", at: 35 },
  { label: "Checking the architecture against your photo", at: 75 },
  { label: "Building your shopping list", at: 95 },
];

// App states: landing -> upload -> questions -> result ("questions" only for
// the New Room Design path; Modify Existing Room goes upload -> result).
// stage tracks the in-flight async task so we can show the right progress.
export default function App() {
  const [cfg, setCfg] = useState(null);
  const [step, setStep] = useState("landing");
  const [mode, setMode] = useState(null); // "new" | "modify", set from the landing screen
  const [stage, setStage] = useState(null); // null | "analyzing" | "saving" | "generating"
  const [error, setError] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);
  const [notice, setNotice] = useState("");
  const [warnings, setWarnings] = useState([]); // soft, non-blocking provider warnings

  const [session, setSession] = useState(null); // { session_id, style, image_url, analysis, questions }
  const [result, setResult] = useState(null);
  // Re-runs whichever request last failed, so a flaky API call during a demo
  // is one click to recover from — the forms keep their inputs meanwhile.
  const [retry, setRetry] = useState(null);

  const busy = stage !== null;

  // "checking" | "ok" | "down" — a failed first contact is shown, not swallowed.
  const [server, setServer] = useState("checking");
  function checkServer() {
    setServer("checking");
    getConfig()
      .then((c) => { setCfg(c); setServer("ok"); })
      .catch(() => { setCfg(null); setServer("down"); });
  }
  useEffect(checkServer, []);

  function absorbWarnings(data) {
    if (data?.warnings?.length) {
      setWarnings((prev) => Array.from(new Set([...prev, ...data.warnings])));
    }
  }

  function beginRequest(nextStage) {
    setStage(nextStage);
    setError("");
    setNotice("");
    setRetry(null);
  }

  // Centralizes what happens when a request fails: session-expired (404) gets
  // its own message + a way back to a clean start; everything else shows the
  // server's friendly message (already translated by the backend) + a retry.
  function handleFailure(e, fallback, retryFn) {
    if (e instanceof ApiError && e.status === 404) {
      setSessionExpired(true);
      setError("Your session has expired (the server may have restarted). Please start over.");
      return;
    }
    setError((e && e.message) || fallback);
    if (retryFn) setRetry(() => retryFn);
  }

  function selectMode(m) {
    setMode(m);
    setError("");
    setNotice("");
    setRetry(null);
    setStep("upload");
  }

  async function handleModify(input) {
    beginRequest("generating");
    setSessionExpired(false);
    try {
      const data = await modifyRoom(input);
      absorbWarnings(data);
      setSession({ session_id: data.session_id, style: data.style, image_url: data.original_image_url });
      setResult(data);
      setStep("result");
    } catch (e) {
      handleFailure(e, "Something went wrong while creating your redesign.", () => handleModify(input));
    } finally {
      setStage(null);
    }
  }

  async function handleUpload(input) {
    beginRequest("analyzing");
    setSessionExpired(false);
    try {
      const data = await uploadRoom(input);
      absorbWarnings(data);
      setSession(data);
      setStep("questions");
    } catch (e) {
      handleFailure(e, "We couldn't analyze that photo. Please try again.", () => handleUpload(input));
    } finally {
      setStage(null);
    }
  }

  async function handleAnswers(answers, message) {
    beginRequest("saving");
    let chat;
    try {
      chat = await sendAnswers({ sessionId: session.session_id, answers, message });
    } catch (e) {
      handleFailure(e, "Something went wrong saving your answers. Please try again.", () =>
        handleAnswers(answers, message)
      );
      setStage(null);
      return;
    }
    absorbWarnings(chat);
    if (!chat.ready_to_generate) {
      setNotice(chat.reply || "Please answer the remaining questions to continue.");
      setStage(null);
      return;
    }
    await runGenerate();
  }

  // Answers are already saved server-side, so a failed render can be retried
  // on its own without re-submitting the questions.
  async function runGenerate() {
    beginRequest("generating");
    try {
      const gen = await generateRedesign({ sessionId: session.session_id });
      absorbWarnings(gen);
      setResult(gen);
      setStep("result");
    } catch (e) {
      handleFailure(e, "Something went wrong while creating your redesign.", runGenerate);
    } finally {
      setStage(null);
    }
  }

  function restart() {
    setSession(null);
    setResult(null);
    setError("");
    setNotice("");
    setWarnings([]);
    setStage(null);
    setSessionExpired(false);
    setRetry(null);
    setMode(null);
    setStep("landing");
  }

  function backToLanding() {
    setMode(null);
    setError("");
    setNotice("");
    setRetry(null);
    setStep("landing");
  }

  // Map app state -> stepper index (0-based over STEPS = [Start, Upload,
  // Preferences, Generate, Results]). The Modify path has no "Preferences"
  // step, so it jumps straight from Upload (1) to Generate (3).
  const currentStep =
    step === "landing" ? 0 :
    step === "result" ? 4 :
    stage === "generating" ? 3 :
    step === "questions" ? 2 :
    1;

  const mockSub = cfg?.using_mock ? "Running on sample data, so this will be quick." : null;

  return (
    <div className="wrap">
      {step === "landing" ? (
        <header className="hero">
          <h1>AI Interior Design Assistant</h1>
          <p className="hero-tagline">See your own room, redesigned.</p>
          <p className="hero-sub">
            Upload a photo. Get an honest verdict on the furniture you already
            have, a redesign painted onto your actual room, and a shopping list
            sized to your space and budget.
          </p>
        </header>
      ) : (
        <>
          <header className="page-title">
            <h1>AI Interior Design Assistant</h1>
          </header>
          <Stepper current={currentStep} />
        </>
      )}

      {server === "down" && (
        <Alert tone="error" title="Can't connect to the design server">
          The page loaded, but the AI server isn't answering. Check your internet
          connection, then try again.
          <div className="alert-actions">
            <button type="button" className="alert-action" onClick={checkServer}>Retry connection</button>
          </div>
        </Alert>
      )}

      {cfg?.using_mock && (
        <div className="banner">
          Demo mode: this server has no AI keys configured, so results are <strong>sample data</strong>.
        </div>
      )}

      {warnings.length > 0 && (
        <Alert
          tone="notice"
          title="Please note"
          onDismiss={() => setWarnings([])}
        >
          {warnings.length === 1 ? (
            warnings[0]
          ) : (
            <ul className="alert-list">
              {warnings.map((w) => <li key={w}>{w}</li>)}
            </ul>
          )}
        </Alert>
      )}

      {error && (
        <Alert tone="error" title="That didn't work" onDismiss={() => setError("")}>
          {error}
          <div className="alert-actions">
            {!sessionExpired && retry && (
              <button type="button" className="alert-action" onClick={() => retry()} disabled={busy}>
                Try again
              </button>
            )}
            <button type="button" className="alert-action" onClick={restart}>
              {sessionExpired ? "Start over" : "Start over instead"}
            </button>
          </div>
        </Alert>
      )}
      {notice && (
        <Alert tone="notice" title="Almost there" onDismiss={() => setNotice("")}>
          {notice}
        </Alert>
      )}

      {/* Forms stay mounted (just hidden) while a request runs, so a failure
          never throws away the photo, answers or instruction already given. */}
      <div className="step-view" key={step === "upload" ? `upload-${mode}` : step}>
        {step === "landing" && <LandingScreen onSelect={selectMode} />}

        {step === "upload" && mode === "new" && (
          <>
            {stage === "analyzing" && (
              <div className="card">
                <ProgressPanel title="Analyzing your room" sub={mockSub || "Usually 15–40 seconds."} steps={ANALYZE_STEPS} />
              </div>
            )}
            <div hidden={stage === "analyzing"}>
              <UploadStep onSubmit={handleUpload} busy={busy} />
            </div>
          </>
        )}

        {step === "upload" && mode === "modify" && (
          <>
            {stage === "generating" && (
              <div className="card">
                <ProgressPanel title="Creating your redesign" sub={mockSub || "Usually 1–2 minutes — the render is checked against your photo before you see it."} steps={MODIFY_STEPS} />
              </div>
            )}
            <div hidden={stage === "generating"}>
              <ModifyStep onSubmit={handleModify} onBack={backToLanding} busy={busy} />
            </div>
          </>
        )}

        {step === "questions" && session && (
          <>
            {stage === "generating" && (
              <div className="card">
                <ProgressPanel title="Generating your redesign" sub={mockSub || "Usually 1–2 minutes — the render is checked against your photo before you see it."} steps={GENERATE_STEPS} />
              </div>
            )}
            <div hidden={stage === "generating"}>
              <AnalysisCard
                originalUrl={session.image_url}
                style={session.style}
                analysis={session.analysis}
              />
              <QuestionForm
                questions={session.questions}
                onSubmit={handleAnswers}
                busy={busy}
              />
            </div>
          </>
        )}

        {step === "result" && result && (
          <ResultView
            result={result}
            originalUrl={session?.image_url}
            onRestart={restart}
          />
        )}
      </div>
    </div>
  );
}
