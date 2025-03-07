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
    }

    set hass(hass) {
      this._hass = hass;
      this.render();
    }

    render() {
      if (!this._hass) return;

      this.shadowRoot.innerHTML = `
        <style>
          :host {
            display: block;
            padding: 16px;
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
        </style>
        <div class="card">
          <div class="card-header">
            <h2>Duplicate Video Finder</h2>
          </div>
          <div class="info-text">
            <p>This tool automatically scans all directories under <code>/home/*</code> for duplicate video files.</p>
          </div>
          <div class="form-group">
            <label for="extensions">Video extensions (comma separated)</label>
            <input type="text" id="extensions" value=".mp4, .avi, .mkv, .mov, .wmv, .flv, .webm">
          </div>
          <button id="scan-button" ${this._isScanning ? 'disabled' : ''}>
            ${this._isScanning ? 'Scanning...' : 'Start Scan'}
          </button>
          <div id="results" style="margin-top: 16px;">
            <p>Click "Start Scan" to find duplicate videos in all /home/* directories.</p>
          </div>
        </div>
      `;

      const scanButton = this.shadowRoot.querySelector("#scan-button");
      scanButton.addEventListener("click", () => this._startScan());
      
      // Add event listeners for group expansion if we have results
      const groupHeaders = this.shadowRoot.querySelectorAll('.group-header');
      groupHeaders.forEach(header => {
        header.addEventListener('click', (e) => {
          const group = e.currentTarget.closest('.duplicate-group');
          group.classList.toggle('expanded');
        });
      });
    }

    _startScan() {
      if (this._isScanning) return;
      
      this._isScanning = true;
      this.render();
      
      const extensionsInput = this.shadowRoot.querySelector("#extensions");
      const resultsContainer = this.shadowRoot.querySelector("#results");
      
      const extensions = extensionsInput.value.split(",").map(ext => ext.trim()).filter(Boolean);
      
      resultsContainer.innerHTML = "<p>Scanning for duplicate videos in /home/* directories...</p>";
      
      // Call the service
      this._hass.callService("duplicate_video_finder", "find_duplicates", {
        video_extensions: extensions
      }).then(() => {
        this._isScanning = false;
        
        // Try to get the results from hass.data
        if (this._hass.data?.duplicate_video_finder?.duplicates) {
          const duplicates = this._hass.data.duplicate_video_finder.duplicates;
          this._displayResults(duplicates);
        } else {
          resultsContainer.innerHTML = "<p>Scan complete! Check Home Assistant logs for results.</p>";
        }
        
        this.render();
      }).catch(error => {
        this._isScanning = false;
        resultsContainer.innerHTML = `<p>Error: ${error.message}</p>`;
        this.render();
      });
    }
    
    _displayResults(duplicates) {
      const resultsContainer = this.shadowRoot.querySelector("#results");
      const duplicateGroups = Object.entries(duplicates);
      
      if (duplicateGroups.length === 0) {
        resultsContainer.innerHTML = `
          <p>No duplicate videos found in /home/* directories.</p>
        `;
        return;
      }
      
      let html = `
        <div style="margin-bottom: 16px;">
          <p>Found ${duplicateGroups.length} groups of duplicate files.</p>
        </div>
      `;
      
      duplicateGroups.forEach(([hash, files]) => {
        html += `
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
        `;
      });
      
      resultsContainer.innerHTML = html;
      
      // Re-add event listeners for group expansion
      const groupHeaders = this.shadowRoot.querySelectorAll('.group-header');
      groupHeaders.forEach(header => {
        header.addEventListener('click', (e) => {
          const group = e.currentTarget.closest('.duplicate-group');
          group.classList.toggle('expanded');
        });
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