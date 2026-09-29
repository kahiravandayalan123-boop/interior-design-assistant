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
  { label: "Analyzing furniture, layout and lighting", at: 2 },
  { label: "Writing follow-up questions for your room", at: 12 },
];
const GENERATE_STEPS = [
  { label: "Writing the design brief", at: 0 },
  { label: "Rendering the redesigned room", at: 8 },
  { label: "Matching products to your budget", at: 45 },
];
const MODIFY_STEPS = [
  { label: "Analyzing your room", at: 0 },
  { label: "Applying your requested change", at: 10 },
  { label: "Rendering the redesigned room", at: 18 },
  { label: "Matching products to your budget", at: 55 },
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

  useEffect(() => {
    getConfig().then(setCfg).catch(() => setCfg(null));
  }, []);

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
      <header>
        <h1>AI Interior Design Assistant</h1>
        <p>
          Design a room from scratch, or tell us what to change about one you
          already have — either way, get an AI redesign with a matching
          shopping list.
        </p>
      </header>

      <Stepper current={currentStep} />

      {cfg?.using_mock && (
        <div className="banner">
          Running on <strong>mock responses</strong>
          {cfg.anthropic_ready ? " for image generation" : ""} — add
          {!cfg.anthropic_ready && <code>ANTHROPIC_API_KEY</code>}
          {!cfg.anthropic_ready && !cfg.openai_ready && " and "}
          {!cfg.openai_ready && <code>OPENAI_API_KEY</code>} to
          <code>backend/.env</code> and restart the backend for the real thing.
        </div>
      )}

      {warnings.length > 0 && (
        <Alert
          tone="notice"
          title={warnings.length === 1 ? "Using a sample for one step" : "Using samples for some steps"}
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
                <ProgressPanel title="Analyzing your room" sub={mockSub || "Usually 10–30 seconds."} steps={ANALYZE_STEPS} />
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
                <ProgressPanel title="Creating your redesign" sub={mockSub || "Usually 40–90 seconds — the image render is the slow part."} steps={MODIFY_STEPS} />
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
                <ProgressPanel title="Generating your redesign" sub={mockSub || "Usually 30–80 seconds — the image render is the slow part."} steps={GENERATE_STEPS} />
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
