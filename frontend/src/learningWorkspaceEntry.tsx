// Reuse the existing authenticated pages, providers and API workflows in full.
// A separate document entry keeps their styles isolated from the learning home.
import LegacyEntry from "./legacyEntry";
import "./selfLearning/workspace.css";

document.documentElement.dataset.learningWorkspace = "true";

export default LegacyEntry;
