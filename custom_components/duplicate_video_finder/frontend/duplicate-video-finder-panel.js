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
      this._version = "1.1.8";
      
      // State properties with defaults
      this._isScanning = false;
      this._isPaused = false;
      this._progress = 0;
      this._currentFile = "";
      this._duplicates = null;
      this._stateInitialized = false;
      this._scanStarted = false;
      this._startTime = null;
      this._debugMode = false;
      this._pollCount = 0;
      this._lastServiceCall = null;
      
      // Initialize UI
      this.render();
    }

    set hass(hass) {
      // Store previous hass for comparison
      const oldHass = this._hass;
      this._hass = hass;
      
      // Log states for debugging
      if (this._isScanning && this._debugMode) {
        console.log("Current hass states:", hass.states);
      }
      
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
      // Return if hass doesn't exist
      if (!hass) {
        return;
      }

      // Try to get state from sensor entity 
      const scanState = 
        hass.states['sensor.duplicate_video_finder_scan_state'] ||
        hass.states['sensor.duplicate_video_finder'];
      
      if (this._debugMode) {
        console.log("Checking scan state entity:", scanState);
      }
      
      if (scanState) {
        if (this._debugMode) {
          console.log("Found scan state entity:", scanState.entity_id, scanState);
        }
        
        const attributes = scanState.attributes || {};
        
        // Skip unavailable entities
        if (scanState.state === 'unavailable') {
          if (this._debugMode) {
            console.log("Entity is unavailable, waiting for state initialization");
          }
          // Don't clear scanning state if we initiated a scan
          if (this._scanStarted) {
            return;
          }
        }
        
        // Update scan state properties based on the sensor state
        this._isScanning = scanState.state === 'scanning';
        this._isPaused = scanState.state === 'paused';
        
        // Get progress from attributes
        if (attributes.progress !== undefined) {
          this._progress = parseFloat(attributes.progress || 0);
        }
        
        // Get current file from attributes
        if (attributes.current_file) {
          this._currentFile = attributes.current_file;
        }
        
        // Update duplicates if available
        if (attributes.found_duplicates) {
          this._duplicates = attributes.found_duplicates;
        }
        
        // If we were scanning but now we're not, clear polling
        if (this._scanStarted && !this._isScanning && scanState.state !== 'unavailable') {
          this._scanStarted = false;
          if (this._debugMode) {
            console.log("Scan completed, clearing polling");
          }
          this._clearPolling();
        }
      } else if (this._debugMode) {
        console.log("No scan state entity found");
      }
      
      // If we have a scan in progress but no entity yet, keep the UI in scanning state
      if (this._scanStarted && (!scanState || scanState.state === 'unavailable')) {
        // Calculate elapsed time
        const elapsed = (Date.now() - this._startTime) / 1000;
        
        if (elapsed > 30 && elapsed <= 120) {
          this._currentFile = `Waiting for scan to start... (${Math.floor(elapsed)}s)`;
        } else if (elapsed > 120) {
          // Only after 2 minutes we consider it failed
          this._isScanning = false;
          this._scanStarted = false;
          this._currentFile = "Scan failed to start properly. Please check Home Assistant logs.";
          this._clearPolling();
        }
      }
    }

    _hasStateChanged(oldHass) {
      // Always return true when first initializing
      if (!oldHass || !this._stateInitialized) {
        return true;
      }

      // Check for state changes in possible entities
      const oldScanState = 
        oldHass.states['duplicate_video_finder.scan_state'] ||
        oldHass.states['sensor.duplicate_video_finder_scan_state'] ||
        oldHass.states['sensor.duplicate_video_finder'];
        
      const newScanState = 
        this._hass.states['duplicate_video_finder.scan_state'] ||
        this._hass.states['sensor.duplicate_video_finder_scan_state'] ||
        this._hass.states['sensor.duplicate_video_finder'];
      
      // If entity appearance/disappearance has changed, render
      if ((!oldScanState && newScanState) || (oldScanState && !newScanState)) {
        return true;
      }
      
      // If state changes during scanning, always render
      if (this._isScanning) {
        return true;
      }
      
      // If no states to compare, check for elapsed time updates during scan
      if (!oldScanState && !newScanState && this._scanStarted) {
        return true;
      }
      
      // If no states to compare and not scanning, use local state
      if (!oldScanState || !newScanState) {
        return false;
      }
      
      const oldAttributes = oldScanState.attributes || {};
      const newAttributes = newScanState.attributes || {};
      
      // Compare relevant properties
      return (
        oldScanState.state !== newScanState.state ||
        this._getProgress(oldAttributes) !== this._getProgress(newAttributes) ||
        this._getCurrentFile(oldAttributes) !== this._getCurrentFile(newAttributes) ||
        JSON.stringify(this._getDuplicates(oldAttributes)) !== 
          JSON.stringify(this._getDuplicates(newAttributes))
      );
    }
    
    // Helper methods to extract attributes consistently
    _getProgress(attributes) {
      return parseFloat(attributes.progress || attributes.scan_progress || 
             attributes.processed_percentage || 0);
    }
    
    _getCurrentFile(attributes) {
      return attributes.current_file || attributes.file || 
             attributes.processing_file || '';
    }
    
    _getDuplicates(attributes) {
      return attributes.found_duplicates || attributes.duplicates || {};
    }

    connectedCallback() {
      // Render the UI if it's empty
      if (!this.shadowRoot.innerHTML) {
        this.render();
      }
      
      // Set up polling if we're scanning
      if (this._isScanning || this._scanStarted) {
        this._setupPolling();
      }
      
      // Force state update if hass is available
      if (this._hass) {
        this._updateScanState(this._hass);
        this.render();
      }
      
      // Enable triple-click on version to enable debug mode
      const versionElement = this.shadowRoot.querySelector('.version');
      if (versionElement) {
        versionElement.addEventListener('click', (e) => {
          if (e.detail === 3) {
            this._debugMode = !this._debugMode;
            console.log(`Debug mode ${this._debugMode ? 'enabled' : 'disabled'}`);
            
            // Show debug info
            if (this._debugMode) {
              console.log("Current hass:", this._hass);
              console.log("Current state:", {
                isScanning: this._isScanning,
                isPaused: this._isPaused,
                progress: this._progress,
                currentFile: this._currentFile,
                scanStarted: this._scanStarted,
                startTime: this._startTime,
                pollCount: this._pollCount
              });
            }
            
            // Add a debug indicator to version
            versionElement.textContent = `v${this._version}${this._debugMode ? ' (Debug)' : ''}`;
          }
        });
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
      if (this._isScanning || this._scanStarted) {
        this._updateTimer = setInterval(() => {
          // Increment poll count
          this._pollCount++;
          
          if (this._hass) {
            // For debugging
            if (this._debugMode && this._pollCount % 5 === 0) {
              console.log(`Polling (${this._pollCount}):`, {
                isScanning: this._isScanning,
                isPaused: this._isPaused,
                progress: this._progress,
                currentFile: this._currentFile,
                scanStarted: this._scanStarted,
                entities: Object.keys(this._hass.states)
                  .filter(id => id.includes('duplicate_video_finder'))
              });
            }
            
            // Update state and render
            this._updateScanState(this._hass);
            this.render();
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

    _renderScanningUI() {
      const statusText = this._isPaused ? 'Paused' : 'Scanning';
      const progressPercent = Math.min(100, Math.max(0, this._progress)).toFixed(1);
      
      // Show elapsed time if scan has started
      let elapsedTimeHtml = '';
      if (this._startTime) {
        const elapsed = Math.floor((Date.now() - this._startTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        elapsedTimeHtml = `
          <div class="scan-elapsed">
            Elapsed time: ${minutes}m ${seconds}s
          </div>
        `;
      }
      
      return `
        <div class="scan-info">
          <div class="scan-status">${statusText} (${progressPercent}% complete)</div>
          <div>Current file: ${this._currentFile || 'Initializing...'}</div>
          ${elapsedTimeHtml}
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
          .scan-elapsed {
            margin-top: 8px;
            font-size: 0.9em;
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
          button.secondary {
            background-color: var(--light-primary-color);
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
        
        <div class="version">v${this._version}${this._debugMode ? ' (Debug)' : ''}</div>
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
      this._currentFile = 'Starting scan...';
      this._scanStarted = true;
      this._startTime = Date.now();
      this._pollCount = 0;
      this.render();
      
      // For debugging
      if (this._debugMode) {
        console.log("Starting scan:", {
          extensions,
          maxCpu,
          batchSize
        });
      }
      
      // Set up polling before service call
      this._setupPolling();
      
      // Call the service
      this._lastServiceCall = Date.now();
      this._hass.callService('duplicate_video_finder', 'find_duplicates', {
        video_extensions: extensions,
        max_cpu_percent: maxCpu,
        batch_size: batchSize
      })
      .then(() => {
        // Service call successful
        if (this._debugMode) {
          console.log("Service call successful");
        }
      })
      .catch(error => {
        // Reset UI on error
        this._isScanning = false;
        this._scanStarted = false;
        console.error('Error starting scan:', error);
        
        // Show error message
        const errorMsg = document.createElement('div');
        errorMsg.style.color = 'red';
        errorMsg.style.marginTop = '16px';
        errorMsg.textContent = `Error starting scan: ${error.message || 'Unknown error'}`;
        
        // Add to UI
        const content = this.shadowRoot.querySelector('.content');
        if (content) {
          content.appendChild(errorMsg);
          // Remove after 5 seconds
          setTimeout(() => {
            if (content.contains(errorMsg)) {
              content.removeChild(errorMsg);
            }
          }, 5000);
        }
        
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