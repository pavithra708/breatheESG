import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [records, setRecords] = useState([]);
  const [dataSources, setDataSources] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [uploading, setUploading] = useState(false);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
  const TENANT_ID = 1; // Default tenant for demo

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard/metrics/?tenant_id=${TENANT_ID}`);
      const data = await res.json();
      setMetrics(data);

      const recordsRes = await fetch(`${API_URL}/records/?tenant_id=${TENANT_ID}`);
      const recordsData = await recordsRes.json();
      setRecords(recordsData.results);

      const sourcesRes = await fetch(`${API_URL}/dashboard/data_sources/?tenant_id=${TENANT_ID}`);
      const sourcesData = await sourcesRes.json();
      setDataSources(sourcesData.results);
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
    }
  };

  const handleUpload = async (sourceType, file) => {
    if (!file) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('tenant_id', TENANT_ID);
      formData.append('uploaded_by', 'analyst@company.com');

      const endpoint = `${API_URL}/upload/upload_${sourceType}/`;
      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        alert(
          `Successfully uploaded ${result.rows_processed} rows. Quality Score: ${result.data_quality_score}%`
        );
        fetchDashboard();
      } else {
        alert('Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Upload error: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  const approveRecord = async (recordId) => {
    try {
      const response = await fetch(`${API_URL}/records/${recordId}/approve/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changed_by: 'analyst@company.com' }),
      });

      if (response.ok) {
        fetchDashboard();
      }
    } catch (error) {
      console.error('Approval error:', error);
    }
  };

  const lockRecord = async (recordId) => {
    try {
      const response = await fetch(`${API_URL}/records/${recordId}/lock/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changed_by: 'system' }),
      });

      if (response.ok) {
        fetchDashboard();
      }
    } catch (error) {
      console.error('Lock error:', error);
    }
  };

  return (
    <div className="App">
      <header className="header">
        <h1>ESG Data Ingestion Platform</h1>
        <nav className="nav">
          <button
            onClick={() => {
              setCurrentView('home');
              fetchDashboard();
            }}
            className={currentView === 'home' ? 'active' : ''}
          >
            Dashboard
          </button>
          <button
            onClick={() => setCurrentView('upload')}
            className={currentView === 'upload' ? 'active' : ''}
          >
            Upload Data
          </button>
          <button
            onClick={() => setCurrentView('review')}
            className={currentView === 'review' ? 'active' : ''}
          >
            Review ({metrics?.pending_review || 0})
          </button>
        </nav>
      </header>

      <main className="main">
        {/* Home/Dashboard View */}
        {currentView === 'home' && metrics && (
          <div className="dashboard">
            <h2>Intake Dashboard</h2>

            <div className="metrics-grid">
              <div className="metric-card">
                <h3>{metrics.total_records}</h3>
                <p>Total Records</p>
              </div>
              <div className="metric-card pending">
                <h3>{metrics.pending_review}</h3>
                <p>Pending Review</p>
              </div>
              <div className="metric-card flagged">
                <h3>{metrics.flagged}</h3>
                <p>Flagged Issues</p>
              </div>
              <div className="metric-card approved">
                <h3>{metrics.approved}</h3>
                <p>Approved</p>
              </div>
              <div className="metric-card locked">
                <h3>{metrics.locked}</h3>
                <p>Locked for Audit</p>
              </div>
            </div>

            <div className="data-sources">
              <h3>Recent Uploads</h3>
              <table>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Filename</th>
                    <th>Uploaded By</th>
                    <th>Rows</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {dataSources.slice(0, 5).map((source) => (
                    <tr key={source.id}>
                      <td>
                        <strong>{source.source_type.toUpperCase()}</strong>
                      </td>
                      <td>{source.original_filename}</td>
                      <td>{source.uploaded_by}</td>
                      <td>{source.row_count}</td>
                      <td>
                        <span className={`badge ${source.processing_status}`}>
                          {source.processing_status}
                        </span>
                      </td>
                      <td>{new Date(source.uploaded_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Upload View */}
        {currentView === 'upload' && (
          <div className="upload-section">
            <h2>Upload Source Data</h2>
            <p>Select a source type and upload your CSV file.</p>

            <div className="upload-cards">
              <UploadCard
                title="SAP Upload"
                description="Fuel & Procurement data"
                sourceType="sap"
                onUpload={(file) => handleUpload('sap', file)}
                uploading={uploading}
              />
              <UploadCard
                title="Utility Upload"
                description="Electricity consumption"
                sourceType="utility"
                onUpload={(file) => handleUpload('utility', file)}
                uploading={uploading}
              />
              <UploadCard
                title="Travel Upload"
                description="Corporate travel expenses"
                sourceType="travel"
                onUpload={(file) => handleUpload('travel', file)}
                uploading={uploading}
              />
            </div>
          </div>
        )}

        {/* Review View */}
        {currentView === 'review' && (
          <div className="review-section">
            <h2>Record Review</h2>

            <div className="filter-buttons">
              <button className="filter-btn active">All ({metrics?.total_records})</button>
              <button className="filter-btn pending">Pending ({metrics?.pending_review})</button>
              <button className="filter-btn flagged">Flagged ({metrics?.flagged})</button>
            </div>

            <table className="records-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Activity</th>
                  <th>Value</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Issues</th>
                  <th>Score</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records
                  .filter((r) => r.status === 'pending' || r.status === 'flagged')
                  .map((record) => (
                    <tr
                      key={record.id}
                      className={record.suspicious_flag ? 'suspicious' : ''}
                    >
                      <td>
                        <strong>{record.category}</strong>
                      </td>
                      <td>{record.activity_type}</td>
                      <td>
                        {record.normalized_value} {record.normalized_unit}
                      </td>
                      <td>{record.activity_date}</td>
                      <td>
                        <span className={`badge ${record.status}`}>{record.status}</span>
                      </td>
                      <td>
                        {record.issues.length > 0 ? (
                          <span className="issue-count">{record.issues.length}</span>
                        ) : (
                          <span className="ok">✓</span>
                        )}
                      </td>
                      <td>{record.confidence_score}%</td>
                      <td className="actions">
                        {record.issues.length === 0 && (
                          <>
                            <button
                              className="btn-small approve"
                              onClick={() => approveRecord(record.id)}
                            >
                              Approve
                            </button>
                            <button
                              className="btn-small lock"
                              onClick={() => lockRecord(record.id)}
                            >
                              Lock
                            </button>
                          </>
                        )}
                        {record.issues.length > 0 && (
                          <details className="issue-details">
                            <summary>View Issues</summary>
                            <ul>
                              {record.issues.map((issue, idx) => (
                                <li key={idx} className={`issue-${issue.severity}`}>
                                  <strong>{issue.issue_type}</strong>: {issue.description}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

function UploadCard({ title, description, sourceType, onUpload, uploading }) {
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      onUpload(file);
      e.target.value = '';
    }
  };

  return (
    <div className="upload-card">
      <h3>{title}</h3>
      <p>{description}</p>
      <label className="upload-label">
        <input
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          disabled={uploading}
          hidden
        />
        <span className="upload-button">{uploading ? 'Uploading...' : 'Choose CSV'}</span>
      </label>
    </div>
  );
}

export default App;

