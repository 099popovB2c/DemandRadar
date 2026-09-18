'use strict';

let data = null;
const $ = (selector) => document.querySelector(selector);

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function safeUrl(value) {
  try {
    const url = new URL(String(value), window.location.href);
    if (url.protocol === 'http:' || url.protocol === 'https:') return url.href;
  } catch (_error) {
    return null;
  }
  return null;
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function chip(text) {
  return el('span', text, 'chip');
}

function renderAlerts() {
  const root = $('#alerts');
  root.replaceChildren();
  const alerts = Array.isArray(data?.alerts) ? data.alerts.slice(0, 8) : [];
  for (const alert of alerts) {
    const card = el('article', null, 'card alert');
    card.append(el('b', `Alert ${number(alert.opportunity_score)}`));
    card.append(document.createTextNode(` ${String(alert.topic || '')}`));
    const reasons = Array.isArray(alert.reasons) ? alert.reasons.map(String).join(', ') : '';
    if (reasons) card.append(document.createTextNode(` — ${reasons}`));
    root.append(card);
  }
}

function createExample(example) {
  const item = el('li');
  const url = safeUrl(example?.url);
  const title = String(example?.title || 'Untitled signal');
  if (url) {
    const anchor = el('a', title);
    anchor.href = url;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    item.append(anchor);
  } else {
    item.append(el('span', title));
  }
  const tags = Array.isArray(example?.intent_tags) && example.intent_tags.length
    ? example.intent_tags.map(String).join('/')
    : 'signal';
  item.append(document.createTextNode(' '));
  item.append(el('small', `${String(example?.source || '')} · ${tags} · intent ${number(example?.intent_score)}`));
  return item;
}

function createCard(opportunity) {
  const trend = opportunity?.trend || { state: 'new' };
  const state = ['new', 'rising', 'stable', 'falling'].includes(trend.state) ? trend.state : 'new';
  const card = el('article', null, `card trend-${state}`);
  card.append(el('div', number(opportunity?.opportunity_score), 'score'));
  card.append(el('h2', opportunity?.topic || 'uncategorized'));

  const chips = el('div', null, 'chips');
  const sources = Array.isArray(opportunity?.sources) ? opportunity.sources : [];
  for (const source of sources) chips.append(chip(source));
  const delta = trend.score_delta;
  const deltaText = delta === null || delta === undefined ? '' : ` ${number(delta) > 0 ? '+' : ''}${number(delta)}`;
  chips.append(chip(`${state}${deltaText}`));
  for (const key of Object.keys(opportunity?.intent_mix || {})) chips.append(chip(key));
  card.append(chips);

  const mentions = number(opportunity?.mentions);
  const engagement = number(opportunity?.engagement);
  const intent = number(opportunity?.demand_intent);
  const freshness = Math.round(number(opportunity?.freshness) * 100);
  card.append(el('p', `${mentions} mentions · ${engagement} engagement · intent ${intent}/10 · freshness ${freshness}%`, 'meta'));

  const bar = el('div', null, 'bar');
  const fill = el('i');
  fill.style.width = `${Math.max(0, Math.min(100, number(opportunity?.opportunity_score)))}%`;
  bar.append(fill);
  card.append(bar);

  const components = opportunity?.components || {};
  card.append(el(
    'p',
    `Frequency ${number(components.frequency)} · Engagement ${number(components.engagement)} · Diversity ${number(components.source_diversity)} · Intent ${number(components.intent)}`,
    'components'
  ));

  const examples = el('ul', null, 'examples');
  for (const example of Array.isArray(opportunity?.examples) ? opportunity.examples : []) {
    examples.append(createExample(example));
  }
  card.append(examples);
  return card;
}

function sortedRows() {
  const query = $('#filter').value.toLowerCase();
  const source = $('#source').value;
  const trend = $('#trend').value;
  const sort = $('#sort').value;
  const rows = (Array.isArray(data?.opportunities) ? data.opportunities : []).filter((row) => {
    const topic = String(row?.topic || '').toLowerCase();
    const sources = Array.isArray(row?.sources) ? row.sources : [];
    const state = row?.trend?.state;
    return (!query || topic.includes(query)) && (!source || sources.includes(source)) && (!trend || state === trend);
  });

  rows.sort((a, b) => {
    if (sort === 'delta') return number(b?.trend?.score_delta, -999) - number(a?.trend?.score_delta, -999);
    if (sort === 'intent') return number(b?.demand_intent) - number(a?.demand_intent);
    if (sort === 'mentions') return number(b?.mentions) - number(a?.mentions);
    return number(b?.opportunity_score) - number(a?.opportunity_score);
  });
  return rows;
}

function render() {
  if (!data) return;
  const grid = $('#grid');
  grid.replaceChildren();
  const rows = sortedRows().slice(0, 60);
  if (!rows.length) {
    grid.append(el('p', 'No matching opportunities.'));
    return;
  }
  for (const row of rows) grid.append(createCard(row));
}

function renderMeta() {
  const coverage = data?.coverage || {};
  const items = Array.isArray(data?.items) ? data.items.length : 0;
  const queries = Array.isArray(data?.queries) ? data.queries.map(String).join(' | ') : '';
  const successRate = Math.round(number(coverage.success_rate, 1) * 100);
  $('#meta').textContent = `${items} unique signals · ${queries} · source success ${successRate}%`;
}

async function load() {
  try {
    const response = await fetch('/data', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    renderMeta();
    renderAlerts();
    render();
  } catch (error) {
    const meta = $('#meta');
    meta.className = 'error';
    meta.textContent = `Could not load dashboard data: ${error.message}`;
  }
}

for (const id of ['filter', 'source', 'trend', 'sort']) {
  $('#' + id).addEventListener('input', render);
}

load();
