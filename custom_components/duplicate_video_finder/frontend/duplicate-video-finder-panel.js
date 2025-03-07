class DuplicateVideoFinderPanel extends HTMLElement {
    constructor() {
        super();
        this._hass = null;
        this._duplicates = null;
    }

    set hass(hass) {
        this._hass = hass;
        this._duplicates = hass.data.duplicate_video_finder?.duplicates || {};
        this.update();
    }

    update() {
        if (!this._duplicates) {
            this.innerHTML = `
                <ha-card>
                    <div class="card-content">
                        <p>No duplicate videos found. Use the service to scan for duplicates.</p>
                    </div>
                </ha-card>
            `;
            return;
        }

        const duplicateGroups = Object.entries(this._duplicates);
        
        if (duplicateGroups.length === 0) {
            this.innerHTML = `
                <ha-card>
                    <div class="card-content">
                        <p>No duplicate videos found.</p>
                    </div>
                </ha-card>
            `;
            return;
        }

        this.innerHTML = `
            <ha-card>
                <div class="card-content">
                    <h2>Duplicate Video Files</h2>
                    ${duplicateGroups.map(([hash, files]) => `
                        <div class="duplicate-group">
                            <h3>Hash: ${hash}</h3>
                            <ul>
                                ${files.map(file => `
                                    <li>${file}</li>
                                `).join('')}
                            </ul>
                        </div>
                    `).join('')}
                </div>
            </ha-card>
        `;
    }
}

customElements.define('duplicate-video-finder-panel', DuplicateVideoFinderPanel);

window.customCards = window.customCards || [];
window.customCards.push({
    type: 'duplicate-video-finder-panel',
    name: 'Duplicate Video Finder',
    preview: true,
}); 