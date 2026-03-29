import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import Fire from './pages/Fire';
import Tax from './pages/Tax';
import Couple from './pages/Couple';
import Audit from './pages/Audit';
import './index.css';

function AppLayout() {
  const location = useLocation();
  const isLanding = location.pathname === '/';

  return (
    <div className="app-layout">
      {!isLanding && <Sidebar />}
      <main className={`main-content ${isLanding ? 'main-content-full' : ''}`}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/fire" element={<Fire />} />
          <Route path="/tax" element={<Tax />} />
          <Route path="/couple" element={<Couple />} />
          <Route path="/audit" element={<Audit />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}

export default App;
