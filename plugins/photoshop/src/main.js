/* eslint-env browser, node */

const { entrypoints } = require('uxp');
const photoshop = require('photoshop');
const fs = require('uxp').storage.localFileSystem;

const CONFIG_FILENAME = 'config.json';

async function readSharedConfig() {
  const userFolder = await fs.getDataFolder();
  try {
    const file = await userFolder.getEntry(CONFIG_FILENAME);
    const contents = await file.read();
    return JSON.parse(contents);
  } catch (error) {
    console.warn('Falling back to default config', error);
    return {
      api_base_url: 'https://game-asset-db.example.com/api'
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
  });
  if (!response.ok) {
    throw new Error(`Failed to load assets: ${response.status}`);
  }
  return response.json();
}

async function placeAsset(asset) {
  const config = await readSharedConfig();
  const endpoint = new URL(`/assets/${asset.id}/import`, config.api_base_url);
  const response = await fetch(endpoint.href, { method: 'POST' });
  if (!response.ok) {
    throw new Error('Failed to request asset import');
  }
  const payload = await response.json();
  const document = await photoshop.app.activeDocument;
  await document.activeLayers[0].name = asset.name;
  console.log('Received import payload', payload);
  // TODO: Download and place the binary into Photoshop once storage endpoints are defined.
}

function renderPanel(rootNode) {
  rootNode.innerHTML = `
    <style>
      .container { display: flex; flex-direction: column; height: 100%; padding: 12px; }
      .asset-list { flex: 1; overflow: auto; margin-top: 8px; border: 1px solid #444; }
      .asset-item { padding: 8px; border-bottom: 1px solid #333; cursor: pointer; }
      .asset-item.selected { background: #1473e6; color: #fff; }
      .actions { margin-top: 8px; display: flex; gap: 8px; }
    </style>
    <div class="container">
      <form id="search-form">
        <sp-textfield placeholder="Search textures" id="search-field"></sp-textfield>
      </form>
      <div class="asset-list" id="asset-list"></div>
      <div class="actions">
        <sp-button id="refresh-button" variant="secondary">Refresh</sp-button>
        <sp-button id="import-button" variant="cta">Place in Document</sp-button>
      </div>
    </div>
  `;

  const list = rootNode.querySelector('#asset-list');
  const field = rootNode.querySelector('#search-field');
  const refreshButton = rootNode.querySelector('#refresh-button');
  const importButton = rootNode.querySelector('#import-button');
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
        div.textContent = `${asset.name} (v${asset.version})`;
        list.appendChild(div);
      }
    } catch (error) {
      console.error(error);
      list.innerHTML = `<div class="asset-item">${error.message}</div>`;
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

  importButton.addEventListener('click', async () => {
    const selected = list.querySelector('.asset-item.selected');
    if (!selected) {
      console.warn('No asset selected');
      return;
    }
    const asset = {
      id: selected.dataset.assetId,
      name: selected.textContent,
    };
    try {
      await placeAsset(asset);
    } catch (error) {
      console.error('Failed to place asset', error);
    }
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
      show(event) {
        renderPanel(event.node);
      },
    },
  },
});
