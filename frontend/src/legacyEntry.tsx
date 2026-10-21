// Kept isolated for rollback, existing export tooling and gradual API integration.
import App from "./stitch/App";
import { AuthProvider } from "./context/AuthContext";
import "./stitch/styles.css";

export default function LegacyEntry() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}
