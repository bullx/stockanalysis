import { Navigate, Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import Home from "./pages/Home";
import Live from "./pages/Live";
import ReportPage from "./pages/Report";
import History from "./pages/History";
import Scorecard from "./pages/Scorecard";
import Ticker from "./pages/Ticker";
import Watch from "./pages/Watch";

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/run/:jobId" element={<Live />} />
        <Route path="/report/:jobId" element={<ReportPage />} />
        <Route path="/archive/:reportId" element={<ReportPage archived />} />
        <Route path="/history" element={<History />} />
        <Route path="/scorecard" element={<Scorecard />} />
        <Route path="/watch" element={<Watch />} />
        <Route path="/ticker/:ticker" element={<Ticker />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
