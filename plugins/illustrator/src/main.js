/* eslint-env browser, node */

const { entrypoints } = require('uxp');
const fs = require('uxp').storage.localFileSystem;

const CONFIG_FILENAME = 'config.json';

async function readSharedConfig() {
  const userFolder = await fs.getDataFolder();
  try {
    const file = await userFolder.getEntry(CONFIG_FILENAME);
    const contents = await file.read();
    return JSON.parse(contents);
  } catch (error) {
    console.warn('Failed to load shared config, falling back to defaults', error);
    return {
      api_base_url: 'https://game-asset-db.example.com/api',
    };
  }
}

async function fetchAssets(query) {
  const config = await readSharedConfig();
  const endpoint = new URL('/assets', config.api_base_url);
  if (query) {
    endpoint.searchParams.set('query', query);
  }
  const response = await fetch(endpoint.href, {
    headers: { 'Accept': 'application/json' },
    method: 'GET',
  });
  if (!response.ok) {
    throw new Error(`Asset request failed: ${response.status}`);
  }
  return response.json();
}

function renderPanel(rootNode) {
  rootNode.innerHTML = `
    <style>
      .container { padding: 16px; display: flex; flex-direction: column; height: 100%; }
      .asset-list { flex: 1; overflow: auto; margin-top: 8px; border: 1px solid #333; }
      .asset-item { padding: 8px; border-bottom: 1px solid #444; cursor: pointer; }
      .actions { margin-top: 8px; display: flex; gap: 8px; }
    </style>
    <div class="container">
      <form id="search-form">
        <sp-textfield placeholder="Search assets" id="search-field"></sp-textfield>
      </form>
      <div class="asset-list" id="asset-list"></div>
      <div class="actions">
        <sp-button id="refresh-button" variant="secondary">Refresh</sp-button>
        <sp-button id="import-button" variant="cta">Import</sp-button>
      </div>
    </div>
  `;

  const list = rootNode.querySelector('#asset-list');
  const field = rootNode.querySelector('#search-field');
  const importButton = rootNode.querySelector('#import-button');
  const refreshButton = rootNode.querySelector('#refresh-button');
  const form = rootNode.querySelector('#search-form');

  async function populateAssets(query) {
    list.innerHTML = '<div class="asset-item">Loading…</div>';
    try {
      const response = await fetchAssets(query);
      const items = response.items || [];
      list.innerHTML = '';
      if (!items.length) {
        list.innerHTML = '<div class="asset-item">No assets found.</div>';
        return;
      }
      for (const asset of items) {
        const div = document.createElement('div');
        div.className = 'asset-item';
        div.dataset.assetId = asset.id;
        div.innerHTML = `<strong>${asset.name}</strong><br/><span>Version ${asset.version}</span>`;
        list.appendChild(div);
      }
    } catch (error) {
      console.error(error);
      list.innerHTML = `<div class="asset-item">Failed to load assets: ${error.message}</div>`;
    }
  }

  list.addEventListener('click', (event) => {
    if (event.target instanceof HTMLElement) {
      const item = event.target.closest('.asset-item');
      if (item) {
        for (const child of list.children) {
          child.classList.remove('selected');
        }
        item.classList.add('selected');
      }
    }
  });

  importButton.addEventListener('click', () => {
    const selected = list.querySelector('.asset-item.selected');
    if (!selected) {
      console.warn('No asset selected');
      return;
    }
    const assetId = selected.dataset.assetId;
    console.log('Requesting Illustrator import for asset', assetId);
    // Actual import pipeline implemented in future iterations via BridgeTalk/local helper.
  });

  refreshButton.addEventListener('click', () => populateAssets(field.value));
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    populateAssets(field.value);
  });

  populateAssets();
}

entrypoints.setup({
  panels: {
    gameAssetDbPanel: {
      create(contentRoot) {
        renderPanel(contentRoot);
      },
    },
  },
});
