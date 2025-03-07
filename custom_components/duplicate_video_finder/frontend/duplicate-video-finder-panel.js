customElements.define(
  "duplicate-video-finder-panel",
  class DuplicateVideoFinderPanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {};
      this._duplicates = null;
      this._isScanning = false;
      this._isPaused = false;
      this._progress = 0;
      this._currentFile = "";
      this._updateTimer = null;
      this._eventListenersAttached = false;
      this._version = "1.1.0"; // Version number
    }

    set hass(hass) {
      const oldHass = this._hass;
      this._hass = hass;
      
      // Check scan state
      if (hass.data?.duplicate_video_finder?.scan_state) {
        const scanState = hass.data.duplicate_video_finder.scan_state;
        this._isScanning = scanState.is_scanning;
        this._isPaused = scanState.is_paused;
        this._progress = scanState.processed_files * 100;
        this._currentFile = scanState.current_file;
        
        // If we have results and scan is complete, update duplicates
        if (!this._isScanning && scanState.found_duplicates && Object.keys(scanState.found_duplicates).length > 0) {
          this._duplicates = scanState.found_duplicates;
        }
      }
      
      // Check for duplicates
      if (!this._duplicates && hass.data?.duplicate_video_finder?.duplicates) {
        this._duplicates = hass.data.duplicate_video_finder.duplicates;
      }
      
      // Only re-render if something relevant has changed
      const shouldUpdate = 
        !oldHass || 
        this._isScanning !== (oldHass.data?.duplicate_video_finder?.scan_state?.is_scanning || false) ||
        this._isPaused !== (oldHass.data?.duplicate_video_finder?.scan_state?.is_paused || false) ||
        Math.abs(this._progress - (oldHass.data?.duplicate_video_finder?.scan_state?.processed_files || 0) * 100) > 1 ||
        this._currentFile !== (oldHass.data?.duplicate_video_finder?.scan_state?.current_file || "");
      
      if (shouldUpdate) {
        this.render();
      }
      
      // Set up polling for progress updates during scanning
      this._setupPolling();
    }

    connectedCallback() {
      if (!this.shadowRoot.innerHTML) {
        this.render();
      }
      this._setupPolling();
    }

    disconnectedCallback() {
      this._clearPolling();
      this._removeEventListeners();
    }
    
    _setupPolling() {
      // Clear existing timer if any
      this._clearPolling();
      
      // Set up new timer if scanning
      if (this._isScanning && !this._updateTimer) {
        this._updateTimer = setInterval(() => {
          if (this._hass) {
            // Fetch latest state
            const scanState = this._hass.data?.duplicate_video_finder?.scan_state;
            if (scanState) {
              this._isScanning = scanState.is_scanning;
              this._isPaused = scanState.is_paused;
              this._progress = scanState.processed_files * 100;
              this._currentFile = scanState.current_file;
              this.render();
            }
          }
        }, 1000);
      }
    }
    
    _clearPolling() {
      if (this._updateTimer) {
        clearInterval(this._updateTimer);
        this._updateTimer = null;
      }
    }

    render() {
      if (!this._hass) return;

      this.shadowRoot.innerHTML = `
        <style>
          :host {
            display: block;
            padding: 16px;
            position: relative;
            min-height: calc(100vh - 32px);
          }
          .card {
            background-color: var(--card-background-color, white);
            border-radius: 4px;
            box-shadow: 0 2px 2px 0 rgba(0,0,0,.14),0 1px 5px 0 rgba(0,0,0,.12),0 3px 1px -2px rgba(0,0,0,.2);
            padding: 16px;
            margin-bottom: 16px;
          }
          .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
          }
          .card-header h2 {
            margin: 0;
            font-size: 24px;
            font-weight: 400;
          }
          .button-container {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
          }
          button {
            background-color: var(--primary-color, #03a9f4);
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 14px;
            cursor: pointer;
          }
          button:hover {
            background-color: var(--dark-primary-color, #0288d1);
          }
          button:disabled {
            background-color: var(--disabled-text-color, #bdbdbd);
            cursor: not-allowed;
          }
          button.secondary {
            background-color: #757575;
          }
          button.secondary:hover {
            background-color: #616161;
          }
          button.warning {
            background-color: #f44336;
          }
          button.warning:hover {
            background-color: #d32f2f;
          }
          .form-group {
            margin-bottom: 16px;
          }
          label {
            display: block;
            margin-bottom: 8px;
          }
          input {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
          }
          .info-text {
            margin-bottom: 16px;
            color: var(--secondary-text-color, #666);
          }
          .progress-container {
            margin-top: 16px;
            margin-bottom: 16px;
          }
          .progress-bar {
            height: 8px;
            background-color: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
          }
          .progress-bar-fill {
            height: 100%;
            background-color: var(--primary-color, #03a9f4);
            width: ${this._progress}%;
            transition: width 0.3s ease;
          }
          .progress-text {
            margin-top: 8px;
            font-size: 14px;
            color: var(--secondary-text-color, #666);
          }
          .current-file {
            margin-top: 8px;
            font-size: 12px;
            color: var(--secondary-text-color, #666);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .duplicate-group {
            border: 1px solid #eee;
            border-radius: 4px;
            margin-bottom: 15px;
            overflow: hidden;
          }
          .group-header {
            background: #f5f5f5;
            padding: 10px 15px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
          }
          .group-content {
            padding: 0 15px;
            display: none;
          }
          .duplicate-group.expanded .group-content {
            display: block;
          }
          .file-item {
            padding: 10px 0;
            border-bottom: 1px solid #eee;
          }
          .file-item:last-child {
            border-bottom: none;
          }
          .file-name {
            font-weight: 500;
            margin-bottom: 5px;
          }
          .file-path {
            font-size: 12px;
            color: #666;
            word-break: break-all;
          }
          .advanced-options {
            margin-top: 16px;
            border-top: 1px solid #eee;
            padding-top: 16px;
          }
          .advanced-options-header {
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
          }
          .advanced-options-header h3 {
            margin: 0;
            font-size: 16px;
            font-weight: 500;
          }
          .advanced-options-content {
            margin-top: 16px;
            display: none;
          }
          .advanced-options.expanded .advanced-options-content {
            display: block;
          }
          .advanced-options-toggle {
            margin-right: 8px;
            transition: transform 0.3s;
          }
          .advanced-options.expanded .advanced-options-toggle {
            transform: rotate(90deg);
          }
          .row {
            display: flex;
            gap: 16px;
            margin-bottom: 16px;
          }
          .col {
            flex: 1;
          }
          .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            margin-left: 8px;
          }
          .status-badge.scanning {
            background-color: #4caf50;
            color: white;
          }
          .status-badge.paused {
            background-color: #ff9800;
            color: white;
          }
          .version {
            position: fixed;
            bottom: 16px;
            right: 16px;
            font-size: 12px;
            color: var(--secondary-text-color, #666);
            opacity: 0.8;
          }
        </style>
        <div class="card">
          <div class="card-header">
            <h2>
              Duplicate Video Finder
              ${this._isScanning ? 
                `<span class="status-badge ${this._isPaused ? 'paused' : 'scanning'}">${this._isPaused ? 'Paused' : 'Scanning'}</span>` : 
                ''}
            </h2>
          </div>
          <div class="info-text">
            <p>This tool automatically scans all directories under <code>/home/*</code> for duplicate video files.</p>
          </div>
          
          ${this._isScanning ? this._renderScanningUI() : this._renderScanForm()}
          
          <div class="advanced-options">
            <div class="advanced-options-header" id="advanced-toggle">
              <span class="advanced-options-toggle">▶</span>
              <h3>Advanced Options</h3>
            </div>
            <div class="advanced-options-content">
              <div class="row">
                <div class="col">
                  <div class="form-group">
                    <label for="max-cpu">Max CPU Usage (%)</label>
                    <input type="number" id="max-cpu" value="70" min="10" max="100" ${this._isScanning ? 'disabled' : ''}>
                  </div>
                </div>
                <div class="col">
                  <div class="form-group">
                    <label for="batch-size">Batch Size</label>
                    <input type="number" id="batch-size" value="100" min="10" max="1000" ${this._isScanning ? 'disabled' : ''}>
                  </div>
                </div>
              </div>
              <div class="form-group">
                <label for="extensions">Video Extensions (comma separated)</label>
                <input type="text" id="extensions" value=".mp4, .avi, .mkv, .mov, .wmv, .flv, .webm" ${this._isScanning ? 'disabled' : ''}>
              </div>
            </div>
          </div>
          
          <div id="results" style="margin-top: 16px;">
            ${this._renderResults()}
          </div>
        </div>
        <div class="version">v${this._version}</div>
      `;

      // Add event listeners
      this._removeEventListeners();
      this._attachEventListeners();
    }
    
    _renderScanForm() {
      return `
        <button id="scan-button">Start Scan</button>
      `;
    }
    
    _renderScanningUI() {
      return `
        <div class="progress-container">
          <div class="progress-bar">
            <div class="progress-bar-fill"></div>
          </div>
          <div class="progress-text">
            ${this._isPaused ? 'Paused' : 'Scanning'}: ${this._progress.toFixed(1)}% complete
          </div>
          ${this._currentFile ? `
            <div class="current-file">
              Current file: ${this._currentFile}
            </div>
          ` : ''}
        </div>
        <div class="button-container">
          ${this._isPaused ? 
            `<button id="resume-button">Resume Scan</button>` : 
            `<button id="pause-button">Pause Scan</button>`
          }
          <button id="cancel-button" class="warning">Cancel Scan</button>
        </div>
      `;
    }
    
    _renderResults() {
      if (this._isScanning) {
        return '';
      }
      
      if (!this._duplicates || Object.keys(this._duplicates).length === 0) {
        return `<p>Click "Start Scan" to find duplicate videos in all /home/* directories.</p>`;
      }
      
      const duplicateGroups = Object.entries(this._duplicates);
      let totalDuplicates = 0;
      
      duplicateGroups.forEach(([hash, files]) => {
        totalDuplicates += files.length - 1; // Subtract 1 to count only duplicates
      });
      
      return `
        <div style="margin-bottom: 16px;">
          <p>Found ${duplicateGroups.length} groups with a total of ${totalDuplicates} duplicate files.</p>
        </div>
        ${duplicateGroups.map(([hash, files]) => `
          <div class="duplicate-group">
            <div class="group-header">
              <span>${files.length} duplicate files</span>
              <span>${hash.substring(0, 8)}...</span>
            </div>
            <div class="group-content">
              ${files.map(file => {
                const parts = file.split('/');
                const filename = parts[parts.length - 1];
                const directory = parts.slice(0, -1).join('/');
                
                return `
                  <div class="file-item">
                    <div class="file-name">${filename}</div>
                    <div class="file-path">${directory}</div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `).join('')}
      `;
    }
    
    _removeEventListeners() {
      // Remove existing event listeners to prevent duplicates
      if (this._eventListenersAttached) {
        const scanButton = this.shadowRoot.querySelector("#scan-button");
        if (scanButton) {
          scanButton.removeEventListener("click", this._boundStartScan);
        }
        
        const pauseButton = this.shadowRoot.querySelector("#pause-button");
        if (pauseButton) {
          pauseButton.removeEventListener("click", this._boundPauseScan);
        }
        
        const resumeButton = this.shadowRoot.querySelector("#resume-button");
        if (resumeButton) {
          resumeButton.removeEventListener("click", this._boundResumeScan);
        }
        
        const cancelButton = this.shadowRoot.querySelector("#cancel-button");
        if (cancelButton) {
          cancelButton.removeEventListener("click", this._boundCancelScan);
        }
        
        const advancedToggle = this.shadowRoot.querySelector("#advanced-toggle");
        if (advancedToggle) {
          advancedToggle.removeEventListener("click", this._boundToggleAdvanced);
        }
        
        const groupHeaders = this.shadowRoot.querySelectorAll('.group-header');
        groupHeaders.forEach(header => {
          header.removeEventListener('click', this._boundToggleGroup);
        });
        
        this._eventListenersAttached = false;
      }
    }

    _attachEventListeners() {
      // Create bound methods if they don't exist
      if (!this._boundStartScan) {
        this._boundStartScan = this._startScan.bind(this);
        this._boundPauseScan = this._pauseScan.bind(this);
        this._boundResumeScan = this._resumeScan.bind(this);
        this._boundCancelScan = this._cancelScan.bind(this);
        this._boundToggleAdvanced = this._toggleAdvanced.bind(this);
        this._boundToggleGroup = this._toggleGroup.bind(this);
      }
      
      // Scan button
      const scanButton = this.shadowRoot.querySelector("#scan-button");
      if (scanButton) {
        scanButton.addEventListener("click", this._boundStartScan);
      }
      
      // Pause button
      const pauseButton = this.shadowRoot.querySelector("#pause-button");
      if (pauseButton) {
        pauseButton.addEventListener("click", this._boundPauseScan);
      }
      
      // Resume button
      const resumeButton = this.shadowRoot.querySelector("#resume-button");
      if (resumeButton) {
        resumeButton.addEventListener("click", this._boundResumeScan);
      }
      
      // Cancel button
      const cancelButton = this.shadowRoot.querySelector("#cancel-button");
      if (cancelButton) {
        cancelButton.addEventListener("click", this._boundCancelScan);
      }
      
      // Advanced options toggle
      const advancedToggle = this.shadowRoot.querySelector("#advanced-toggle");
      if (advancedToggle) {
        advancedToggle.addEventListener("click", this._boundToggleAdvanced);
      }
      
      // Add event listeners for group expansion
      const groupHeaders = this.shadowRoot.querySelectorAll('.group-header');
      groupHeaders.forEach(header => {
        header.addEventListener('click', this._boundToggleGroup);
      });
      
      this._eventListenersAttached = true;
    }
    
    _toggleAdvanced(e) {
      const advancedOptions = this.shadowRoot.querySelector(".advanced-options");
      advancedOptions.classList.toggle("expanded");
    }
    
    _toggleGroup(e) {
      const group = e.currentTarget.closest('.duplicate-group');
      group.classList.toggle('expanded');
    }

    _startScan() {
      if (this._isScanning) return;
      
      // Get advanced options
      const extensionsInput = this.shadowRoot.querySelector("#extensions");
      const maxCpuInput = this.shadowRoot.querySelector("#max-cpu");
      const batchSizeInput = this.shadowRoot.querySelector("#batch-size");
      
      const extensions = extensionsInput.value.split(",").map(ext => ext.trim()).filter(Boolean);
      const maxCpu = parseInt(maxCpuInput.value) || 70;
      const batchSize = parseInt(batchSizeInput.value) || 100;
      
      // Reset progress
      this._progress = 0;
      this._currentFile = "";
      this._isScanning = true;
      this._isPaused = false;
      
      this.render();
      
      // Call the service
      this._hass.callService("duplicate_video_finder", "find_duplicates", {
        video_extensions: extensions,
        max_cpu_percent: maxCpu,
        batch_size: batchSize
      }).catch(error => {
        this._isScanning = false;
        const resultsContainer = this.shadowRoot.querySelector("#results");
        if (resultsContainer) {
          resultsContainer.innerHTML = `<p>Error: ${error.message}</p>`;
        }
        this.render();
      });
      
      // Set up polling
      this._setupPolling();
    }
    
    _pauseScan() {
      if (!this._isScanning || this._isPaused) return;
      
      this._isPaused = true;
      this.render();
      
      // Call the service
      this._hass.callService("duplicate_video_finder", "pause_scan", {}).catch(error => {
        this._isPaused = false;
        console.error("Error pausing scan:", error);
        this.render();
      });
    }
    
    _resumeScan() {
      if (!this._isScanning || !this._isPaused) return;
      
      this._isPaused = false;
      this.render();
      
      // Call the service
      this._hass.callService("duplicate_video_finder", "resume_scan", {}).catch(error => {
        this._isPaused = true;
        console.error("Error resuming scan:", error);
        this.render();
      });
    }
    
    _cancelScan() {
      if (!this._isScanning) return;
      
      if (confirm("Are you sure you want to cancel the scan?")) {
        // Call the service
        this._hass.callService("duplicate_video_finder", "cancel_scan", {}).catch(error => {
          console.error("Error cancelling scan:", error);
        });
      }
    }
  }
);

window.customCards = window.customCards || [];
window.customCards.push({
    type: 'duplicate-video-finder-panel',
    name: 'Duplicate Video Finder',
    preview: true,
}); 