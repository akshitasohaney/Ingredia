import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import { uploadScan, submitScanText } from '../api.js';
import './ScanUpload.css';

function ScanUpload() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('image'); // 'image' | 'text'

  // Image upload state
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);

  // Text state
  const [text, setText] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function handleFileChange(e) {
    const f = e.target.files[0];
    if (!f) return;
    if (!f.type.startsWith('image/')) {
      setError('Only image files are supported.');
      return;
    }
    setFile(f);
    setError(null);
    const reader = new FileReader();
    reader.onload = ev => setPreview(ev.target.result);
    reader.readAsDataURL(f);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (mode === 'image' && !file) {
      setError('Please select an image file.');
      return;
    }
    if (mode === 'text' && text.trim().length < 2) {
      setError('Please enter the ingredient list text.');
      return;
    }

    setLoading(true);
    try {
      let scan;
      if (mode === 'image') {
        scan = await uploadScan(file);
      } else {
        scan = await submitScanText(text.trim());
      }
      navigate(`/scan/review/${scan.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="su-page">
      <div className="su-header">
        <h1 className="su-title">Scan a label</h1>
        <p className="su-sub">
          Upload a photo of a product label or paste the ingredient list.
          Ingredia will extract and analyse each ingredient.
        </p>
      </div>

      {/* Mode tabs */}
      <div className="su-tabs">
        <button
          className={`su-tab ${mode === 'image' ? 'su-tab--active' : ''}`}
          onClick={() => { setMode('image'); setError(null); }}
        >
          Upload image
        </button>
        <button
          className={`su-tab ${mode === 'text' ? 'su-tab--active' : ''}`}
          onClick={() => { setMode('text'); setError(null); }}
        >
          Paste text
        </button>
      </div>

      <form className="su-form" onSubmit={handleSubmit}>
        {mode === 'image' && (
          <div className="su-upload-area">
            <label className="su-dropzone" htmlFor="label-file">
              {preview ? (
                <img src={preview} alt="Label preview" className="su-preview" />
              ) : (
                <>
                  <div className="su-dropzone__icon">◻</div>
                  <p className="su-dropzone__text">Click to select an image</p>
                  <p className="su-dropzone__hint">JPG, PNG, WEBP — max 20 MB</p>
                </>
              )}
            </label>
            <input
              id="label-file"
              type="file"
              accept="image/*"
              className="su-file-input"
              onChange={handleFileChange}
            />
            {file && (
              <p className="su-filename">
                {file.name} ({(file.size / 1024).toFixed(0)} KB)
                <button
                  type="button"
                  className="su-clear"
                  onClick={() => { setFile(null); setPreview(null); }}
                >Remove</button>
              </p>
            )}
          </div>
        )}

        {mode === 'text' && (
          <div className="su-text-area">
            <label className="su-text-label" htmlFor="ing-text">
              Paste the full ingredient list
            </label>
            <textarea
              id="ing-text"
              className="su-textarea"
              rows={8}
              placeholder="Aqua, Glycerin, Niacinamide, Sodium Hyaluronate…"
              value={text}
              onChange={e => setText(e.target.value)}
            />
            <p className="su-text-hint">
              Ingredients are typically comma-separated. Copy them exactly as they appear on the label.
            </p>
          </div>
        )}

        {error && <div className="su-error">{error}</div>}

        <div className="su-actions">
          <button
            type="submit"
            className="btn btn-primary su-submit"
            disabled={loading}
          >
            {loading ? 'Processing…' : 'Extract & review ingredients'}
          </button>
          {loading && <Loader />}
        </div>
      </form>

      <div className="su-disclaimer">
        <strong>OCR accuracy:</strong> Text extracted from images may contain errors.
        You will be able to review and correct each matched ingredient before analysis.
      </div>
    </main>
  );
}

export default ScanUpload;
