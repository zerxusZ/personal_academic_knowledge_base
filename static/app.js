'use strict';

// ── Cluster colour palette ─────────────────────────────────────────────────
const PALETTE = [
  '#4f6ef7','#10b981','#f59e0b','#ef4444','#8b5cf6',
  '#06b6d4','#ec4899','#84cc16','#f97316','#6366f1',
];
const clusterColor = (idx) => PALETTE[idx % PALETTE.length];

// Tag category → CSS class
const TAG_CLASS = {
  topics:'topic', methods:'method', concepts:'concept',
  domain:'domain', problem_type:'problem',
};

// ── State ──────────────────────────────────────────────────────────────────
let allSources = [];
let allClusters = [];

// ── Utils ──────────────────────────────────────────────────────────────────
function toast(msg, ms = 3500) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add('hidden'), ms);
}

function setLoader(visible, msg = 'Analysing source…') {
  document.getElementById('loader').classList.toggle('hidden', !visible);
  document.getElementById('loader-msg').textContent = msg;
}

function llmParam() {
  const v = document.getElementById('llm-select').value;
  return v ? `?llm=${v}` : '';
}

// ── Render helpers ─────────────────────────────────────────────────────────
function tagChipsHtml(tags, maxPerCat = 3) {
  const chips = [];
  for (const [cat, cls] of Object.entries(TAG_CLASS)) {
    (tags[cat] || []).slice(0, maxPerCat).forEach(t =>
      chips.push(`<span class="tag-chip ${cls}">${t}</span>`)
    );
  }
  return chips.join('');
}

function sourceIcon(ctype) {
  const icons = { arxiv_id:'📄', arxiv_url:'📄', doi:'📑', url:'🔗', text:'📝' };
  return icons[ctype] || '📄';
}

// ── Sidebar source list ────────────────────────────────────────────────────
function renderSidebarSources(sources) {
  const list = document.getElementById('source-list');
  document.getElementById('source-count').textContent = sources.length;

  if (!sources.length) {
    list.innerHTML = '<p style="padding:12px 10px;color:#9ca3af;font-size:.82rem">No sources yet.<br>Add one above!</p>';
    return;
  }

  const clusterColorMap = {};
  allClusters.forEach((c, i) => { clusterColorMap[c.id] = clusterColor(i); });

  list.innerHTML = sources.map(s => {
    const dotColor = s.cluster_id ? clusterColorMap[s.cluster_id] || '#d1d5db' : '#d1d5db';
    const clusterLabel = s.cluster_label ? `· ${s.cluster_label}` : '';
    return `
    <div class="source-item" data-id="${s.id}">
      <div class="src-icon">${sourceIcon(s.content_type)}</div>
      <div class="src-body">
        <div class="src-title">${escHtml(s.title)}</div>
        <div class="src-meta">${s.year ? s.year + ' ' : ''}${clusterLabel}</div>
      </div>
      <div class="src-cluster-dot" style="background:${dotColor}" title="${escHtml(s.cluster_label||'')}"></div>
      <button class="del-btn" data-id="${s.id}" title="Remove">✕</button>
    </div>`;
  }).join('');

  list.querySelectorAll('.source-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.classList.contains('del-btn')) return;
      openDrawer(el.dataset.id);
    });
  });
  list.querySelectorAll('.del-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      deleteSource(btn.dataset.id);
    });
  });
}

// ── Cluster grid ───────────────────────────────────────────────────────────
function renderClusters(clusters, sources) {
  const welcome = document.getElementById('welcome');
  const view = document.getElementById('cluster-view');

  if (!sources.length) {
    welcome.classList.remove('hidden');
    view.classList.add('hidden');
    return;
  }
  welcome.classList.add('hidden');
  view.classList.remove('hidden');

  const srcMap = Object.fromEntries(sources.map(s => [s.id, s]));
  const grid = document.getElementById('cluster-grid');

  // Sort clusters by size descending
  const sorted = [...clusters].sort((a, b) => b.source_ids.length - a.source_ids.length);

  // Unclustered sources (if any)
  const clusteredIds = new Set(clusters.flatMap(c => c.source_ids));
  const unclustered = sources.filter(s => !clusteredIds.has(s.id));

  const blocksHtml = sorted.map((c, i) => {
    const color = clusterColor(i);
    const clusterSources = c.source_ids.map(id => srcMap[id]).filter(Boolean);
    return clusterBlockHtml(c, clusterSources, color);
  });

  if (unclustered.length) {
    const pseudo = { id: '_lone', label: 'Other Sources', dominant_tags: [], source_ids: unclustered.map(s=>s.id), summary: '' };
    blocksHtml.push(clusterBlockHtml(pseudo, unclustered, '#9ca3af'));
  }

  grid.innerHTML = blocksHtml.join('');

  document.getElementById('cluster-count-label').textContent =
    `${clusters.length} topic cluster${clusters.length !== 1 ? 's' : ''} · ${sources.length} source${sources.length !== 1 ? 's' : ''}`;

  grid.querySelectorAll('.source-card').forEach(card => {
    card.addEventListener('click', () => openDrawer(card.dataset.id));
  });
}

function clusterBlockHtml(cluster, sources, color) {
  const tagChips = cluster.dominant_tags.slice(0, 8)
    .map(t => `<span class="tag-chip dominant">${escHtml(t)}</span>`).join('');

  const cards = sources.map(s => `
    <div class="source-card" data-id="${s.id}">
      <div class="source-card-title">${escHtml(s.title)}</div>
      <div class="source-card-meta">${s.authors.slice(0,2).join(', ')}${s.authors.length>2?' et al.':''}${s.year ? ' · ' + s.year : ''}</div>
      <div class="source-card-summary">${escHtml(s.summary || s.raw_text.slice(0, 160) + '…')}</div>
      <div class="source-card-tags">${tagChipsHtml(s.tags)}</div>
    </div>`).join('');

  return `
  <div class="cluster-block">
    <div class="cluster-block-header">
      <div class="cluster-color-bar" style="background:${color}"></div>
      <div>
        <div class="cluster-block-title">${escHtml(cluster.label)}</div>
        ${cluster.summary ? `<div class="cluster-block-summary">${escHtml(cluster.summary)}</div>` : ''}
      </div>
      <span class="count-badge" style="margin-left:auto;flex-shrink:0">${sources.length}</span>
    </div>
    ${tagChips ? `<div class="cluster-dominant-tags">${tagChips}</div>` : ''}
    <div class="cluster-sources">${cards}</div>
  </div>`;
}

// ── Drawer ─────────────────────────────────────────────────────────────────
function openDrawer(sourceId) {
  const source = allSources.find(s => s.id === sourceId);
  if (!source) return;

  const tags = source.tags || {};
  const tagRows = Object.entries(TAG_CLASS).map(([cat, cls]) => {
    const chips = (tags[cat] || []).map(t => `<span class="tag-chip ${cls}">${escHtml(t)}</span>`).join('');
    if (!chips) return '';
    const label = cat.replace('_', ' ');
    return `<div class="tag-row"><span class="tag-category">${label}</span><div class="tag-row-chips">${chips}</div></div>`;
  }).join('');

  const keyConceptsHtml = (source.key_concepts || [])
    .map(k => `<span class="concept-pill">${escHtml(k)}</span>`).join('');

  document.getElementById('drawer-content').innerHTML = `
    <div class="drawer-title">${escHtml(source.title)}</div>
    <div class="drawer-meta">
      ${source.authors.slice(0,4).join(', ')}${source.authors.length>4?' et al.':''}
      ${source.year ? '· ' + source.year : ''}
      ${source.cluster_label ? `· <strong>${escHtml(source.cluster_label)}</strong>` : ''}
    </div>

    ${source.summary ? `
    <div class="drawer-section">
      <h3>Plain-language summary</h3>
      <p class="drawer-summary">${escHtml(source.summary)}</p>
    </div>` : ''}

    ${source.notable_quote ? `
    <div class="drawer-section">
      <h3>Notable passage</h3>
      <div class="drawer-quote">${escHtml(source.notable_quote)}</div>
    </div>` : ''}

    ${keyConceptsHtml ? `
    <div class="drawer-section">
      <h3>Key concepts</h3>
      <div class="key-concepts-list">${keyConceptsHtml}</div>
    </div>` : ''}

    ${tagRows ? `
    <div class="drawer-section">
      <h3>Semantic tags</h3>
      <div class="tags-grid">${tagRows}</div>
    </div>` : ''}

    ${source.url ? `
    <div class="drawer-section">
      <a class="drawer-link" href="${escHtml(source.url)}" target="_blank">↗ Open original source</a>
    </div>` : ''}

    <div class="drawer-section">
      <h3>Raw excerpt</h3>
      <p style="font-size:.8rem;color:#6b7280;line-height:1.6">${escHtml(source.raw_text.slice(0, 600))}${source.raw_text.length>600?'…':''}</p>
    </div>`;

  document.getElementById('drawer').classList.remove('hidden');
  document.getElementById('drawer-overlay').classList.remove('hidden');
  requestAnimationFrame(() => document.getElementById('drawer').classList.add('open'));
}

function closeDrawer() {
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('drawer-overlay').classList.add('hidden');
  setTimeout(() => document.getElementById('drawer').classList.add('hidden'), 260);
}

document.getElementById('drawer-close').addEventListener('click', closeDrawer);
document.getElementById('drawer-overlay').addEventListener('click', closeDrawer);

// ── Data loading ───────────────────────────────────────────────────────────
async function loadAll() {
  const [srcResp, clResp] = await Promise.all([
    fetch('/sources'), fetch('/sources/clusters'),
  ]);
  allSources = await srcResp.json();
  allClusters = await clResp.json();
  renderSidebarSources(allSources);
  renderClusters(allClusters, allSources);
}

// ── Ingest ─────────────────────────────────────────────────────────────────
document.getElementById('ingest-btn').addEventListener('click', async () => {
  const content = document.getElementById('ingest-input').value.trim();
  if (!content) { toast('Paste something first — arXiv ID, URL, or any text.'); return; }

  const body = {
    content,
    title: document.getElementById('ingest-title').value.trim() || undefined,
    hint:  document.getElementById('ingest-hint').value.trim() || undefined,
  };

  const llv = document.getElementById('llm-select').value;
  const qs = llv ? `?llm=${llv}&recluster=true` : '?recluster=true';

  const btn = document.getElementById('ingest-btn');
  btn.disabled = true;
  setLoader(true, 'Reading & tagging source…');

  try {
    const resp = await fetch('/sources' + qs, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(err);
    }
    document.getElementById('ingest-input').value = '';
    document.getElementById('ingest-title').value = '';
    document.getElementById('ingest-hint').value = '';
    setLoader(true, 'Rebuilding clusters…');
    await loadAll();
    toast('Source added and clustered ✓');
  } catch (err) {
    toast('Error: ' + err.message, 6000);
  } finally {
    btn.disabled = false;
    setLoader(false);
  }
});

// ── Delete ─────────────────────────────────────────────────────────────────
async function deleteSource(id) {
  if (!confirm('Remove this source from your knowledge base?')) return;
  await fetch(`/sources/${id}`, { method: 'DELETE' });
  await loadAll();
  toast('Source removed.');
}

// ── Re-cluster ─────────────────────────────────────────────────────────────
document.getElementById('recluster-btn').addEventListener('click', async () => {
  if (!allSources.length) { toast('Add some sources first.'); return; }
  const llv = document.getElementById('llm-select').value;
  const qs = llv ? `?llm=${llv}` : '';
  setLoader(true, 'Re-clustering all sources…');
  try {
    const resp = await fetch('/sources/recluster' + qs, { method: 'POST' });
    allClusters = await resp.json();
    await loadAll();
    toast('Clusters rebuilt ✓');
  } catch (err) {
    toast('Error: ' + err.message, 5000);
  } finally {
    setLoader(false);
  }
});

// ── Export ─────────────────────────────────────────────────────────────────
document.getElementById('export-btn').addEventListener('click', async () => {
  const payload = { sources: allSources, clusters: allClusters, exported_at: new Date().toISOString() };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `knowledge_base_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  toast('Exported ✓');
});

// ── Search ─────────────────────────────────────────────────────────────────
document.getElementById('kb-search').addEventListener('input', e => {
  const q = e.target.value.toLowerCase().trim();
  if (!q) { renderClusters(allClusters, allSources); return; }
  const filtered = allSources.filter(s =>
    s.title.toLowerCase().includes(q) ||
    s.summary.toLowerCase().includes(q) ||
    s.tags.all_tags ? false :   // fallback: check all tag values
    Object.values(s.tags).flat().some(t => t.toLowerCase().includes(q))
  );
  // Build pseudo-clusters for search results
  const pseudo = [{ id:'_search', label:`Results for "${q}"`, dominant_tags:[], source_ids: filtered.map(s=>s.id), summary:'' }];
  renderClusters(pseudo, filtered);
});

// ── Welcome example chips ──────────────────────────────────────────────────
document.querySelectorAll('.example-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.getElementById('ingest-input').value = chip.dataset.val;
    document.getElementById('ingest-input').focus();
  });
});

// ── Escape HTML ────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Init ───────────────────────────────────────────────────────────────────
loadAll();
