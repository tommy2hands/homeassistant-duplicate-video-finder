import { html, LitElement } from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class DuplicateVideoFinderPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      panel: { type: Object },
    };
  }

  render() {
    return html`
      <style>
        :host {
          display: block;
          padding: 0;
          margin: 0;
          width: 100%;
          height: 100%;
        }
        iframe {
          border: 0;
          width: 100%;
          height: 100%;
          display: block;
        }
      </style>
      <iframe
        src="/local/duplicate_video_finder/duplicate-video-finder-panel.html"
        allow="fullscreen"
      ></iframe>
    `;
  }
}

customElements.define("duplicate-video-finder-panel", DuplicateVideoFinderPanel); 