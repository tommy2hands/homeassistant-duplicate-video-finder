customElements.define(
  "duplicate-video-finder-panel",
  class DuplicateVideoFinderPanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {};
      this._duplicates = null;
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
        </style>
        <div class="card">
          <div class="card-header">
            <h2>Duplicate Video Finder</h2>
          </div>
          <div class="form-group">
            <label for="directories">Directories to scan (comma separated)</label>
            <input type="text" id="directories" placeholder="/media/videos, /home/user/movies">
          </div>
          <div class="form-group">
            <label for="extensions">Video extensions (comma separated)</label>
            <input type="text" id="extensions" value=".mp4, .avi, .mkv, .mov, .wmv, .flv, .webm">
          </div>
          <button id="scan-button">Start Scan</button>
          <div id="results" style="margin-top: 16px;">
            <p>Enter directories to scan and click "Start Scan" to find duplicate videos.</p>
          </div>
        </div>
      `;

      const scanButton = this.shadowRoot.querySelector("#scan-button");
      scanButton.addEventListener("click", () => this._startScan());
    }

    _startScan() {
      const directoriesInput = this.shadowRoot.querySelector("#directories");
      const extensionsInput = this.shadowRoot.querySelector("#extensions");
      const resultsContainer = this.shadowRoot.querySelector("#results");
      
      const directories = directoriesInput.value.split(",").map(dir => dir.trim()).filter(Boolean);
      const extensions = extensionsInput.value.split(",").map(ext => ext.trim()).filter(Boolean);
      
      if (directories.length === 0) {
        resultsContainer.innerHTML = "<p>Please enter at least one directory to scan</p>";
        return;
      }
      
      resultsContainer.innerHTML = "<p>Scanning for duplicate videos...</p>";
      
      // Call the service
      this._hass.callService("duplicate_video_finder", "find_duplicates", {
        video_extensions: extensions
      }).then(() => {
        resultsContainer.innerHTML = "<p>Scan complete! Check Home Assistant logs for results.</p>";
      }).catch(error => {
        resultsContainer.innerHTML = `<p>Error: ${error.message}</p>`;
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