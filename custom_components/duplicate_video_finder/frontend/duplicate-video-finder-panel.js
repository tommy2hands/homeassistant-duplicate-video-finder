class DuplicateVideoFinderPanel extends HTMLElement {
    constructor() {
        super();
        this._hass = null;
        this._duplicates = null;
        this._config = {};
        this._isScanning = false;
        this._scanStartTime = null;
        this._attachEventListeners = this._attachEventListeners.bind(this);
        this._startScan = this._startScan.bind(this);
    }

    set hass(hass) {
        this._hass = hass;
        
        // Check if a scan is in progress
        if (this._isScanning && hass.data.duplicate_video_finder?.duplicates) {
            const duplicatesCount = Object.keys(hass.data.duplicate_video_finder.duplicates).length;
            if (duplicatesCount > 0) {
                this._isScanning = false;
                this._duplicates = hass.data.duplicate_video_finder.duplicates;
                this.update();
            }
        } else if (!this._duplicates && hass.data.duplicate_video_finder?.duplicates) {
            this._duplicates = hass.data.duplicate_video_finder.duplicates;
            this.update();
        }
    }

    connectedCallback() {
        if (!this.shadowRoot) {
            this.attachShadow({ mode: 'open' });
            this.update();
        }
    }

    disconnectedCallback() {
        // Clean up event listeners
        const scanButton = this.shadowRoot.querySelector('#scan-button');
        if (scanButton) {
            scanButton.removeEventListener('click', this._startScan);
        }
    }

    _attachEventListeners() {
        const scanButton = this.shadowRoot.querySelector('#scan-button');
        if (scanButton) {
            scanButton.addEventListener('click', this._startScan);
        }

        // Add event listeners for group expansion
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
        this._scanStartTime = new Date();
        this.update();
        
        // Call the service to start scanning
        this._hass.callService('duplicate_video_finder', 'find_duplicates', {});
    }

    _formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) {
            bytes /= 1024;
            i++;
        }
        return `${bytes.toFixed(2)} ${units[i]}`;
    }

    _getFileInfo(filepath) {
        const parts = filepath.split('/');
        const filename = parts[parts.length - 1];
        return {
            name: filename,
            path: filepath,
            directory: parts.slice(0, -1).join('/')
        };
    }

    update() {
        if (!this.shadowRoot) return;
        
        // Define styles
        const style = `
            :host {
                display: block;
                font-family: var(--paper-font-body1_-_font-family);
            }
            .card {
                background-color: var(--card-background-color, white);
                border-radius: var(--ha-card-border-radius, 4px);
                box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0, 0, 0, 0.14), 0 1px 5px 0 rgba(0, 0, 0, 0.12), 0 3px 1px -2px rgba(0, 0, 0, 0.2));
                color: var(--primary-text-color);
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
            .scan-button {
                background-color: var(--primary-color);
                color: var(--text-primary-color);
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                cursor: pointer;
                transition: background-color 0.3s;
            }
            .scan-button:hover {
                background-color: var(--dark-primary-color);
            }
            .scan-button:disabled {
                background-color: var(--disabled-text-color);
                cursor: not-allowed;
            }
            .duplicate-group {
                margin-bottom: 16px;
                border: 1px solid var(--divider-color);
                border-radius: 4px;
                overflow: hidden;
            }
            .group-header {
                background-color: var(--secondary-background-color);
                padding: 12px 16px;
                cursor: pointer;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .group-header h3 {
                margin: 0;
                font-size: 16px;
                font-weight: 500;
            }
            .group-content {
                display: none;
                padding: 0 16px;
            }
            .duplicate-group.expanded .group-content {
                display: block;
            }
            .file-item {
                padding: 12px 0;
                border-bottom: 1px solid var(--divider-color);
            }
            .file-item:last-child {
                border-bottom: none;
            }
            .file-name {
                font-weight: 500;
                margin-bottom: 4px;
            }
            .file-path {
                font-size: 12px;
                color: var(--secondary-text-color);
                word-break: break-all;
            }
            .scanning-indicator {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 32px 16px;
            }
            .spinner {
                border: 4px solid rgba(0, 0, 0, 0.1);
                border-radius: 50%;
                border-top: 4px solid var(--primary-color);
                width: 40px;
                height: 40px;
                animation: spin 2s linear infinite;
                margin-bottom: 16px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .empty-state {
                text-align: center;
                padding: 32px 16px;
                color: var(--secondary-text-color);
            }
            .stats {
                margin-bottom: 16px;
                font-size: 14px;
                color: var(--secondary-text-color);
            }
        `;

        // Create content based on state
        let content = '';
        
        if (this._isScanning) {
            // Scanning in progress
            content = `
                <div class="scanning-indicator">
                    <div class="spinner"></div>
                    <p>Scanning for duplicate videos...</p>
                </div>
            `;
        } else if (!this._duplicates || Object.keys(this._duplicates).length === 0) {
            // No duplicates found
            content = `
                <div class="empty-state">
                    <p>No duplicate videos found. Click the scan button to start searching.</p>
                </div>
            `;
        } else {
            // Display duplicates
            const duplicateGroups = Object.entries(this._duplicates);
            const totalGroups = duplicateGroups.length;
            let totalDuplicates = 0;
            
            duplicateGroups.forEach(([hash, files]) => {
                totalDuplicates += files.length - 1; // Subtract 1 to count only duplicates
            });
            
            content = `
                <div class="stats">
                    Found ${totalGroups} groups with a total of ${totalDuplicates} duplicate files.
                </div>
                ${duplicateGroups.map(([hash, files]) => `
                    <div class="duplicate-group">
                        <div class="group-header">
                            <h3>${files.length} duplicate files</h3>
                            <span>${hash.substring(0, 8)}...</span>
                        </div>
                        <div class="group-content">
                            ${files.map(file => {
                                const fileInfo = this._getFileInfo(file);
                                return `
                                    <div class="file-item">
                                        <div class="file-name">${fileInfo.name}</div>
                                        <div class="file-path">${fileInfo.directory}</div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `).join('')}
            `;
        }

        // Render the complete UI
        this.shadowRoot.innerHTML = `
            <style>${style}</style>
            <div class="card">
                <div class="card-header">
                    <h2>Duplicate Video Finder</h2>
                    <button id="scan-button" class="scan-button" ${this._isScanning ? 'disabled' : ''}>
                        ${this._isScanning ? 'Scanning...' : 'Start Scan'}
                    </button>
                </div>
                ${content}
            </div>
        `;

        // Attach event listeners after rendering
        this._attachEventListeners();
    }
}

customElements.define('duplicate-video-finder-panel', DuplicateVideoFinderPanel);

window.customCards = window.customCards || [];
window.customCards.push({
    type: 'duplicate-video-finder-panel',
    name: 'Duplicate Video Finder',
    preview: true,
}); 