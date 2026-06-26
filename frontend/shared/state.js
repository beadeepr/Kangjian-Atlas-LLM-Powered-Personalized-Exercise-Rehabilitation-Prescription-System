// Shared application state + step navigation.
//
// Kept framework-free: `state` is a plain object mutated in place by app.js
// and the page modules. `goToStep` is split into a thin shell (here, handles
// DOM page switching + step-nav highlight + secondary-page mapping) and a
// per-step loader registry that app.js populates at startup. Page modules
// register their loader via `registerStepLoader`.

export const state = {
  currentStep: "login",
  prescription: null,
  currentAction: null,
  cameraStream: null,
  selectedPainRegions: new Set(),
  poseTracker: null,
  poseInFlight: false,
  pendingPosePayload: null,
  lastPoseSentAt: 0,
  autoPoseEnabled: false,
  currentUser: null,
  auth: null,
  authTab: "login",
  selectedPatientProfileId: null,
  patientProfiles: [],
  profileFormRegions: new Set(),
  profileReturnStep: "intake",
  actionLibrary: [],
  libraryFilters: { q: "", bodyRegion: "", difficulty: "" },
  imagingReports: [],
  voiceEnabled: false,
  trainingStartTime: null,
  trainingTimer: null,
  trainingRepCount: 0,
  trainingSetCount: 0,
  lastRepStatus: null,
  trainingLastScore: null,
  adminEditingId: null,
  adminFilters: { q: "", bodyRegion: "" },
  adminPanelData: null,
  adminScrollFocusTimer: null,
  knowledgeFilters: { q: "", bodyRegion: "" },
  knowledgeArticles: [],
  knowledgeExpandedId: null,
  knowledgeTab: "articles",
  knowledgeQaRegions: new Set(),
  feedbackRating: 0,
  adminUserFilter: { q: "" },
  adminFeedbackFilters: { status: "", category: "" },
};

// Secondary pages (no step-nav button) map onto a nearest main-flow step
// so the step bar still reflects "where am I".
const SECONDARY_STEP_PARENT = {
  profiles: "intake",
  library: "intake",
  progress: "history",
  knowledge: "intake",
  admin: "prescription",
};

const stepLoaders = new Map();
let stepNavEl = null;

export function registerStepLoader(step, loader) {
  if (typeof loader === "function") stepLoaders.set(step, loader);
}

export function setStepNavEl(el) {
  stepNavEl = el;
}

function resolveNavStep(step) {
  return SECONDARY_STEP_PARENT[step] || step;
}

function updateStepNav(step, isReady, hasPrescription, hasAction, poseSupported) {
  if (!stepNavEl) return;
  const navStep = resolveNavStep(step);
  stepNavEl.querySelectorAll(".step-item").forEach((button) => {
    const target = button.dataset.step;
    const isCurrent = target === navStep;
    button.classList.toggle("active", isCurrent);
    if (target === "login") {
      button.disabled = false;
    } else if (!isReady) {
      button.disabled = true;
    } else if (target === "prescription") {
      button.disabled = !hasPrescription;
    } else if (target === "demo") {
      button.disabled = !hasAction;
    } else if (target === "training") {
      button.disabled = !hasAction || !poseSupported;
    } else {
      button.disabled = false;
    }
  });
}

// `ctx` provides the few app-level hooks the nav needs without importing
// app.js (which would create a cycle). Kept intentionally tiny.
export function makeGoToStep(ctx) {
  const {
    isSessionReady,
    setHeaderMenuOpen,
    updateUserIdentity,
    onNavigate,
  } = ctx;

  return function goToStep(step) {
    state.currentStep = step;
    setHeaderMenuOpen(false);
    sessionStorage.setItem("kj_current_step", step);

    document.querySelectorAll(".page").forEach((page) => {
      page.classList.toggle("active", page.id === `page-${step}`);
    });

    updateStepNav(
      step,
      isSessionReady(),
      Boolean(state.prescription),
      Boolean(state.currentAction),
      Boolean(state.currentAction && window.APP_CONFIG?.isPoseSupported?.(state.currentAction.id))
    );

    updateUserIdentity?.();
    onNavigate?.(step);

    const loader = stepLoaders.get(step);
    if (loader) loader();
  };
}
