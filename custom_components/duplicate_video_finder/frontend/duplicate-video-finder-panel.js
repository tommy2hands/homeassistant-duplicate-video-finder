customElements.define(
  "duplicate-video-finder-panel",
  class DuplicateVideoFinderPanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      
      // Basic properties
      this._hass = null;
      this._config = {};
      this._updateTimer = null;
      this._eventListenersAttached = false;
      this._version = "1.1.4";
      
      // State properties with defaults
      this._isScanning = false;
      this._isPaused = false;
      this._progress = 0;
      this._currentFile = "";
      this._duplicates = null;
      this._stateInitialized = false;
      
      // Initialize UI
      this.render();
    }

    set hass(hass) {
      // Store previous hass for comparison
      const oldHass = this._hass;
      this._hass = hass;
      
      // Handle scan state updates
      this._updateScanState(hass);
      
      // Render if state has changed or not initialized yet
      if (!this._stateInitialized || (oldHass && this._hasStateChanged(oldHass))) {
        this.render();
        this._stateInitialized = true;
      }
      
      // Set up polling for updates if scanning
      if (this._isScanning && !this._updateTimer) {
        this._setupPolling();
      }
    }

    _updateScanState(hass) {
      // Return if hass or scan state doesn't exist
      if (!hass || !hass.states || !hass.states['duplicate_video_finder.scan_state']) {
        return;
      }

      // Get state and attributes
      const entity = hass.states['duplicate_video_finder.scan_state'];
      const attributes = entity.attributes || {};
      
      // Update scan state properties
      this._isScanning = entity.state === 'scanning';
      this._isPaused = entity.state === 'paused';
      this._progress = parseFloat(attributes.progress || 0);
      this._currentFile = attributes.current_file || '';
      
      // Update duplicates if available
      if (attributes.found_duplicates) {
        this._duplicates = attributes.found_duplicates;
      }
      
      // Clear polling if scan is complete
      if (!this._isScanning && this._updateTimer) {
        this._clearPolling();
      }
    }

    _hasStateChanged(oldHass) {
      // Check if hass exists
      if (!oldHass || !oldHass.states || !oldHass.states['duplicate_video_finder.scan_state']) {
        return true;
      }

      // Get old state and attributes
      const oldEntity = oldHass.states['duplicate_video_finder.scan_state'];
      const oldAttributes = oldEntity.attributes || {};
      
      // Compare scan state properties
      return this._isScanning !== (oldEntity.state === 'scanning') ||
             this._isPaused !== (oldEntity.state === 'paused') ||
             this._progress !== parseFloat(oldAttributes.progress || 0) ||
             this._currentFile !== (oldAttributes.current_file || '') ||
             JSON.stringify(this._duplicates) !== JSON.stringify(oldAttributes.found_duplicates || {});
    }

    connectedCallback() {
      // Render the UI if it's empty
      if (!this.shadowRoot.innerHTML) {
        this.render();
      }
      
      // Set up polling if we're scanning
      if (this._isScanning) {
        this._setupPolling();
      }
      
      // Force state update if hass is available
      if (this._hass) {
        this._updateScanState(this._hass);
        this.render();
      }
    }

    disconnectedCallback() {
      // Clean up resources but don't reset state
      if (this._updateTimer) {
        this._clearPolling();
      }
      this._removeEventListeners();
    }

    _setupPolling() {
      // Clear existing timer
      this._clearPolling();
      
      // Set up new timer for progress updates
      if (this._isScanning) {
        this._updateTimer = setInterval(() => {
          if (this._hass) {
            // Directly get the latest state
            this._hass.callApi('GET', 'states/duplicate_video_finder.scan_state')
              .then(state => {
                if (state) {
                  // Create a temporary hass object with the scan state
                  const tempHass = {
                    states: {
                      'duplicate_video_finder.scan_state': state
                    }
                  };
                  
                  // Update state and render
                  this._updateScanState(tempHass);
                  this.render();
                }
              })
              .catch(error => {
                console.error("Error polling scan state:", error);
              });
          }
        }, 1000);
      }
    }

    _clearPolling() {
      // Clear the update timer
      if (this._updateTimer) {
        clearInterval(this._updateTimer);
        this._updateTimer = null;
      }
    }

    render() {
      // Basic loading or error state
      if (!this._hass) {
        this.shadowRoot.innerHTML = `
          <div style="padding: 20px; text-align: center;">
            Loading Duplicate Video Finder...
          </div>
        `;
        return;
      }

      // Main UI
      this.shadowRoot.innerHTML = `
        <style>
          .card {
            padding: 16px;
            background: var(--card-background-color, white);
            box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0, 0, 0, 0.14), 0 1px 5px 0 rgba(0, 0, 0, 0.12), 0 3px 1px -2px rgba(0, 0, 0, 0.2));
            border-radius: var(--ha-card-border-radius, 4px);
            margin-bottom: 16px;
          }
          .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
          }
          .title {
            font-size: 1.5rem;
            font-weight: 500;
            color: var(--primary-text-color);
          }
          .progress-bar {
            width: 100%;
            height: 24px;
            background-color: var(--secondary-background-color);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 8px;
          }
          .progress-bar-fill {
            height: 100%;
            background-color: var(--primary-color);
            border-radius: 12px;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            text-align: center;
            min-width: 40px;
          }
          .flex-row {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
          }
          .scan-info {
            margin-bottom: 16px;
            color: var(--secondary-text-color);
          }
          .scan-status {
            color: var(--primary-color);
            font-weight: 500;
          }
          button {
            background-color: var(--primary-color);
            color: var(--text-primary-color);
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.3s ease;
          }
          button:hover {
            background-color: var(--dark-primary-color);
          }
          button:disabled {
            background-color: var(--disabled-color, #ccc);
            cursor: not-allowed;
          }
          .button-icon {
            margin-right: 8px;
          }
          .form-group {
            margin-bottom: 16px;
          }
          .form-control {
            width: 100%;
            padding: 8px;
            border: 1px solid var(--divider-color);
            border-radius: 4px;
            background-color: var(--primary-background-color);
            color: var(--primary-text-color);
          }
          .accordion {
            border: 1px solid var(--divider-color);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 16px;
          }
          .accordion-header {
            background-color: var(--secondary-background-color);
            padding: 12px 16px;
            cursor: pointer;
            font-weight: 500;
            display: flex;
            justify-content: space-between;
            align-items: center;
          }
          .accordion-content {
            padding: 16px;
            display: none;
          }
          .accordion-content.open {
            display: block;
          }
          .duplicate-group {
            margin-bottom: 16px;
            border: 1px solid var(--divider-color);
            border-radius: 4px;
            overflow: hidden;
          }
          .duplicate-group-header {
            background-color: var(--secondary-background-color);
            padding: 12px 16px;
            cursor: pointer;
            font-weight: 500;
            display: flex;
            justify-content: space-between;
            align-items: center;
          }
          .duplicate-group-content {
            padding: 16px;
            display: none;
          }
          .duplicate-group-content.open {
            display: block;
          }
          .duplicate-item {
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--divider-color);
          }
          .duplicate-item:last-child {
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
          }
          .duplicate-path {
            font-family: monospace;
            word-break: break-all;
          }
          .duplicate-info {
            font-size: 0.9em;
            color: var(--secondary-text-color);
          }
          .version {
            position: fixed;
            bottom: 10px;
            right: 10px;
            font-size: 0.8em;
            color: var(--secondary-text-color);
            opacity: 0.7;
          }
        </style>
        
        <div class="card">
          <div class="header">
            <div class="title">Duplicate Video Finder</div>
          </div>
          
          <div class="content">
            ${this._isScanning ? this._renderScanningUI() : this._renderScanForm()}
            ${this._duplicates ? this._renderResults() : ''}
          </div>
        </div>
        
        <div class="version">v${this._version}</div>
      `;
      
      // Attach event listeners after rendering
      this._removeEventListeners();
      this._attachEventListeners();
    }

    _renderScanForm() {
      return `
        <div class="form-group">
          <label for="extensions">Video Extensions (comma separated)</label>
          <input type="text" id="extensions" class="form-control" placeholder="mp4, mkv, avi, mov" value="mp4, mkv, avi, mov">
        </div>
        
        <div class="accordion">
          <div class="accordion-header" id="advanced-header">
            Advanced Options <span>▼</span>
          </div>
          <div class="accordion-content" id="advanced-content">
            <div class="form-group">
              <label for="max-cpu">Max CPU Usage (%)</label>
              <input type="number" id="max-cpu" class="form-control" min="10" max="100" value="70">
            </div>
            <div class="form-group">
              <label for="batch-size">Batch Size</label>
              <input type="number" id="batch-size" class="form-control" min="10" max="1000" value="100">
            </div>
          </div>
        </div>
        
        <button id="start-scan" class="primary">
          <span class="button-icon">▶</span> Start Scan
        </button>
      `;
    }

    _renderScanningUI() {
      const statusText = this._isPaused ? 'Paused' : 'Scanning';
      const progressPercent = Math.min(100, Math.max(0, this._progress)).toFixed(1);
      
      return `
        <div class="scan-info">
          <div class="scan-status">${statusText} (${progressPercent}% complete)</div>
          <div>Current file: ${this._currentFile || 'Initializing...'}</div>
        </div>
        
        <div class="progress-bar">
          <div class="progress-bar-fill" style="width: ${progressPercent}%">${progressPercent}%</div>
        </div>
        
        <div class="flex-row">
          ${this._isPaused 
            ? `<button id="resume-scan" class="primary"><span class="button-icon">▶</span> Resume</button>` 
            : `<button id="pause-scan" class="primary"><span class="button-icon">⏸</span> Pause</button>`
          }
          <button id="cancel-scan" class="secondary"><span class="button-icon">⏹</span> Cancel</button>
        </div>
      `;
    }

    _renderResults() {
      if (!this._duplicates || Object.keys(this._duplicates).length === 0) {
        return `<div style="margin-top: 16px;">No duplicates found.</div>`;
      }
      
      const groupKeys = Object.keys(this._duplicates);
      const totalGroups = groupKeys.length;
      const totalFiles = groupKeys.reduce((total, key) => total + this._duplicates[key].length, 0);
      
      let html = `
        <div style="margin-top: 24px; margin-bottom: 16px;">
          <h3>Duplicates Found</h3>
          <div>${totalGroups} duplicate groups with ${totalFiles} total files</div>
        </div>
      `;
      
      groupKeys.forEach((key, index) => {
        const files = this._duplicates[key];
        html += `
          <div class="duplicate-group">
            <div class="duplicate-group-header" data-group="${index}">
              Group ${index + 1} (${files.length} files) <span>▼</span>
            </div>
            <div class="duplicate-group-content" id="group-${index}">
              ${files.map(file => `
                <div class="duplicate-item">
                  <div class="duplicate-path">${file.path}</div>
                  <div class="duplicate-info">
                    Size: ${this._formatSize(file.size)} | 
                    Created: ${new Date(file.created * 1000).toLocaleString()}
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      });
      
      return html;
    }

    _formatSize(bytes) {
      const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
      if (bytes === 0) return '0 Bytes';
      const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
      return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + sizes[i];
    }

    _removeEventListeners() {
      // Remove event listeners to prevent memory leaks
      this._eventListenersAttached = false;
    }

    _attachEventListeners() {
      if (this._eventListenersAttached) return;
      
      // Start scan button
      const startButton = this.shadowRoot.querySelector('#start-scan');
      if (startButton) {
        startButton.addEventListener('click', () => this._startScan());
      }
      
      // Pause scan button
      const pauseButton = this.shadowRoot.querySelector('#pause-scan');
      if (pauseButton) {
        pauseButton.addEventListener('click', () => this._pauseScan());
      }
      
      // Resume scan button
      const resumeButton = this.shadowRoot.querySelector('#resume-scan');
      if (resumeButton) {
        resumeButton.addEventListener('click', () => this._resumeScan());
      }
      
      // Cancel scan button
      const cancelButton = this.shadowRoot.querySelector('#cancel-scan');
      if (cancelButton) {
        cancelButton.addEventListener('click', () => this._cancelScan());
      }
      
      // Advanced accordion toggle
      const advancedHeader = this.shadowRoot.querySelector('#advanced-header');
      if (advancedHeader) {
        advancedHeader.addEventListener('click', () => this._toggleAdvanced());
      }
      
      // Duplicate group toggles
      const groupHeaders = this.shadowRoot.querySelectorAll('.duplicate-group-header');
      groupHeaders.forEach(header => {
        header.addEventListener('click', (e) => this._toggleGroup(e));
      });
      
      this._eventListenersAttached = true;
    }

    _toggleAdvanced() {
      const content = this.shadowRoot.querySelector('#advanced-content');
      if (content) {
        content.classList.toggle('open');
        
        const header = this.shadowRoot.querySelector('#advanced-header');
        if (header) {
          const arrow = header.querySelector('span');
          if (arrow) {
            arrow.textContent = content.classList.contains('open') ? '▲' : '▼';
          }
        }
      }
    }

    _toggleGroup(e) {
      const header = e.currentTarget;
      const groupIndex = header.getAttribute('data-group');
      const content = this.shadowRoot.querySelector(`#group-${groupIndex}`);
      
      if (content) {
        content.classList.toggle('open');
        
        const arrow = header.querySelector('span');
        if (arrow) {
          arrow.textContent = content.classList.contains('open') ? '▲' : '▼';
        }
      }
    }

    _startScan() {
      // Don't start if already scanning
      if (this._isScanning) return;
      
      // Get scan options
      const extensionsInput = this.shadowRoot.querySelector('#extensions');
      const maxCpuInput = this.shadowRoot.querySelector('#max-cpu');
      const batchSizeInput = this.shadowRoot.querySelector('#batch-size');
      
      // Parse values with defaults
      const extensions = extensionsInput?.value.split(',').map(ext => ext.trim()).filter(Boolean) || ['mp4', 'mkv', 'avi', 'mov'];
      const maxCpu = parseInt(maxCpuInput?.value) || 70;
      const batchSize = parseInt(batchSizeInput?.value) || 100;
      
      // Update UI state immediately
      this._isScanning = true;
      this._isPaused = false;
      this._progress = 0;
      this._currentFile = '';
      this.render();
      
      // Call the service
      this._hass.callService('duplicate_video_finder', 'find_duplicates', {
        video_extensions: extensions,
        max_cpu_percent: maxCpu,
        batch_size: batchSize
      })
      .then(() => {
        // Set up polling for updates
        this._setupPolling();
      })
      .catch(error => {
        // Reset UI on error
        this._isScanning = false;
        console.error('Error starting scan:', error);
        this.render();
      });
    }

    _pauseScan() {
      if (!this._isScanning || this._isPaused) return;
      
      // Update UI immediately
      this._isPaused = true;
      this.render();
      
      // Call the service
      this._hass.callService('duplicate_video_finder', 'pause_scan', {})
        .catch(error => {
          // Reset UI on error
          this._isPaused = false;
          console.error('Error pausing scan:', error);
          this.render();
        });
    }

    _resumeScan() {
      if (!this._isScanning || !this._isPaused) return;
      
      // Update UI immediately
      this._isPaused = false;
      this.render();
      
      // Call the service
      this._hass.callService('duplicate_video_finder', 'resume_scan', {})
        .catch(error => {
          // Reset UI on error
          this._isPaused = true;
          console.error('Error resuming scan:', error);
          this.render();
        });
    }

    _cancelScan() {
      if (!this._isScanning) return;
      
      // Call the service
      this._hass.callService('duplicate_video_finder', 'cancel_scan', {})
        .catch(error => {
          console.error('Error cancelling scan:', error);
        });
    }
  }
);

window.customCards = window.customCards || [];
window.customCards.push({
    type: 'duplicate-video-finder-panel',
    name: 'Duplicate Video Finder',
    preview: true,
}); 