import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home.jsx';
import ProductSearchResults from './pages/ProductSearchResults.jsx';
import ProductDetail from './pages/ProductDetail.jsx';
import IngredientDetail from './pages/IngredientDetail.jsx';
import ScanUpload from './pages/ScanUpload.jsx';
import ScanReview from './pages/ScanReview.jsx';
import RiskAnalysis from './pages/RiskAnalysis.jsx';
import Header from './components/Header.jsx';
import Footer from './components/Footer.jsx';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Header />
      <div className="app-content">
        <Routes>
          <Route path="/"                        element={<Home />} />
          <Route path="/search"                  element={<ProductSearchResults />} />
          <Route path="/product/:id"             element={<ProductDetail />} />
          <Route path="/product/:id/risk"        element={<RiskAnalysis />} />
          <Route path="/ingredient/:id"          element={<IngredientDetail />} />
          <Route path="/scan"                    element={<ScanUpload />} />
          <Route path="/scan/review/:id"         element={<ScanReview />} />
          <Route path="/scan/review/:id/analysis" element={<RiskAnalysis isScanAnalysis />} />
        </Routes>
      </div>
      <Footer />
    </BrowserRouter>
  );
}

export default App;
