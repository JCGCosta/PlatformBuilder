import * as rdflib from 'rdflib';

/**
 * Loads the layout ontology from the provided path and extracts layout
 * configuration plus API settings.
 */
export async function loadLayoutOntology(layoutUrl) {
  const store = rdflib.graph();

  const RDF = rdflib.Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#');

  console.log('Loading layout ontology:', layoutUrl);

  const cacheBustedUrl = `${layoutUrl}?_ts=${Date.now()}`;
  const response = await fetch(cacheBustedUrl, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Failed to fetch layout ontology: ${response.statusText}`);
  }
  const turtleContent = await response.text();

  const baseMatch = turtleContent.match(/@base\s+<([^>]+)>/);
  const layoutPrefixMatch = turtleContent.match(/@prefix\s+layout:\s+<([^>]+)>/);
  const LAYOUT_NS = baseMatch?.[1] || layoutPrefixMatch?.[1] || 'http://example.org/layout#';

  console.log('Detected layout namespace:', LAYOUT_NS);

  const ns = rdflib.Namespace(LAYOUT_NS);

  rdflib.parse(turtleContent, store, LAYOUT_NS, 'text/turtle');

  const findIndividualByType = (className) => {
    const classNode = ns(className);
    const individuals = store.each(undefined, RDF('type'), classNode);
    return individuals.length > 0 ? individuals[0] : null;
  };

  const headerNode      = findIndividualByType('Header');
  const sidebarNode     = findIndividualByType('Sidebar');
  const footerNode      = findIndividualByType('Footer');
  const contentAreaNode = findIndividualByType('ContentArea');
  const layoutNode      = findIndividualByType('Layout');

  const headerTitle        = headerNode      ? store.any(headerNode,      ns('hasTitle'))   : null;
  const headerHeight       = headerNode      ? store.any(headerNode,      ns('hasHeight'))  : null;
  const headerIsFixed      = headerNode      ? store.any(headerNode,      ns('isFixed'))    : null;
  const headerLogoSrc      = headerNode      ? store.any(headerNode,      ns('hasLogoSrc')) : null;
  const headerLogoAlt      = headerNode      ? store.any(headerNode,      ns('hasLogoAlt')) : null;
  const headerLogoHeight   = headerNode      ? store.any(headerNode,      ns('hasLogoHeight')) : null;
  const headerLogoWidth    = headerNode      ? store.any(headerNode,      ns('hasLogoWidth')) : null;
  const sidebarWidth       = sidebarNode     ? store.any(sidebarNode,     ns('hasWidth'))   : null;
  const footerText         = footerNode      ? store.any(footerNode,      ns('hasText'))    : null;
  const footerHeight       = footerNode      ? store.any(footerNode,      ns('hasHeight'))  : null;
  const footerIsFixed      = footerNode      ? store.any(footerNode,      ns('isFixed'))    : null;
  const contentAreaPadding = contentAreaNode ? store.any(contentAreaNode, ns('hasPadding')) : null;

  const apiBaseUrlNode = layoutNode ? store.any(layoutNode, ns('hasApiBaseUrl')) : null;
  const bmOntologyNodes = layoutNode
    ? store.each(layoutNode, ns('hasBusinessModelOntology'), undefined)
    : [];

  const toBool = (value, fallback = true) => {
    if (!value) return fallback;
    const normalized = String(value.value).toLowerCase();
    return normalized === 'true' || normalized === '1';
  };

  const toNumber = (value, fallback) => {
    if (!value) return fallback;
    const parsed = Number.parseInt(value.value, 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  };

  const result = {
    headerTitle:             headerTitle?.value        || null,
    headerHeight:            toNumber(headerHeight, 64),
    headerIsFixed:           toBool(headerIsFixed, true),
    headerLogoSrc:           headerLogoSrc?.value      || null,
    headerLogoAlt:           headerLogoAlt?.value      || 'Logo',
    headerLogoHeight:        headerLogoHeight?.value   || '48px',
    headerLogoWidth:         headerLogoWidth?.value    || 'auto',
    sidebarWidth:            toNumber(sidebarWidth, 200),
    footerText:              footerText?.value         || 'Define layout:hasText in ontology',
    footerHeight:            toNumber(footerHeight, 50),
    footerIsFixed:           toBool(footerIsFixed, true),
    contentAreaPadding:      toNumber(contentAreaPadding, 24),
    apiBaseUrl:              apiBaseUrlNode?.value     || 'http://127.0.0.1:5000',
    businessModelOntologies: bmOntologyNodes.map(n => n.value),
  };

  console.log('Final layout config:', result);
  return result;
}

/**
 * Discovers available views from the provided manifest path.
 * Each entry uses a full "file" path (e.g. "/ontologies/views/...ttl").
 * Supports flat entries and `type: "group"` entries with nested views.
 */
export async function loadViews(manifestUrl) {
  try {
    const response = await fetch(manifestUrl);

    if (!response.ok) {
      console.warn('No manifest.json found at', manifestUrl);
      return [];
    }

    const manifest = await response.json();
    const items = [];

    for (const entry of manifest.views || []) {
      if (entry.type === 'group') {
        items.push({
          type: 'group',
          name: entry.name,
          views: (entry.views || []).map(v => ({
            name: v.name || v.file,
            path: v.file,
          })),
        });
      } else {
        items.push({
          name: entry.name || entry.file,
          path: entry.file,
        });
      }
    }

    console.log('Views discovered from manifest:', items);
    return items;
  } catch (error) {
    console.error('Error discovering views:', error);
    return [];
  }
}
