import { useEffect, useState, useCallback } from 'react';
import * as rdflib from 'rdflib';
import { ConfigProvider, Spin, Alert, Typography } from 'antd';
import enUS from 'antd/locale/en_US';

import { serializeOntologies, findEndpoints } from './lib/index.js';
import { renderUI } from './render/ViewOntologyRenderer.js';
import { loadLayoutOntology, loadViews } from './render/components/layout/LayoutOntologyRenderer.js';
import UIRenderer from './render/components/ui/UIRenderer.jsx';
import MainLayout from './render/components/layout/MainLayout.jsx';

const { Paragraph } = Typography;

const DEFAULT_LAYOUT_ONTOLOGY_URL = '/ontologies/app/layout.ttl';
const DEFAULT_MANIFEST_URL = '/ontologies/app/manifest.json';

function OntologyToUIRuntime({
  layoutOntologyUrl = DEFAULT_LAYOUT_ONTOLOGY_URL,
  manifestUrl = DEFAULT_MANIFEST_URL,
}) {
  const [layoutConfig, setLayoutConfig] = useState(null);
  const [views, setViews] = useState([]);
  const [selectedView, setSelectedView] = useState(null);

  const [uiElements, setUiElements] = useState(null);
  const [apiEndpoints, setApiEndpoints] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function initializeLayout() {
      try {
        setLoading(true);
        setError(null);

        const config = await loadLayoutOntology(layoutOntologyUrl);
        setLayoutConfig(config);
        console.log('Layout config loaded:', config);

        const discoveredViews = await loadViews(manifestUrl);
        setViews(discoveredViews);
        console.log('Views discovered:', discoveredViews);

        const firstView = discoveredViews.find(v => v.type !== 'group') ||
          discoveredViews.flatMap(v => v.type === 'group' ? v.views : [])[0];
        if (firstView) {
          setSelectedView(firstView.path);
        }

      } catch (err) {
        console.error('Error initializing layout:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    initializeLayout();
  }, [layoutOntologyUrl, manifestUrl]);

  useEffect(() => {
    if (!selectedView || !layoutConfig) return;

    async function loadViewContent() {
      try {
        setLoading(true);
        setError(null);

        const store = rdflib.graph();
        const prefixes = {};

        for (const ontologyPath of layoutConfig.businessModelOntologies) {
          console.log('Loading business ontology:', ontologyPath);
          const p = await serializeOntologies(store, ontologyPath);
          Object.assign(prefixes, p);
        }

        const endpoints = await findEndpoints(store, prefixes);
        console.log('Endpoints found:', endpoints);
        setApiEndpoints({ ...endpoints, apiBaseUrl: layoutConfig.apiBaseUrl });

        console.log('Loading view:', selectedView);
        const elements = await renderUI(selectedView);
        console.log('UI elements found:', elements);
        setUiElements(elements);

      } catch (err) {
        console.error('Error loading view:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadViewContent();
  }, [selectedView, layoutConfig]);

  const handleViewSelect = useCallback((viewPath) => {
    console.log('View selected:', viewPath);
    setSelectedView(viewPath);
  }, []);

  if (!layoutConfig) {
    return (
      <ConfigProvider locale={enUS}>
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          background: '#f0f2f5'
        }}>
          <div style={{ textAlign: 'center' }}>
            <Spin size="large" />
            <Paragraph style={{ marginTop: 16 }}>Loading...</Paragraph>
          </div>
        </div>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider locale={enUS}>
      <MainLayout
        layoutConfig={layoutConfig}
        views={views}
        selectedView={selectedView}
        onViewSelect={handleViewSelect}
      >
        {error ? (
          <Alert
            title="Error loading view"
            description={error}
            type="error"
            showIcon
            style={{ margin: 24 }}
          />
        ) : (
          <UIRenderer
            uiElements={uiElements}
            apiEndpoints={apiEndpoints}
            loading={loading}
            error={null}
          />
        )}
      </MainLayout>
    </ConfigProvider>
  );
}

export default OntologyToUIRuntime;
