import { createRoot } from 'react-dom/client';
import { OntologyToUIRuntime } from '@smart-lem/ontology-to-ui';

createRoot(document.getElementById('root')).render(
  <OntologyToUIRuntime layoutOntologyUrl="/ontologies/app/layout.ttl" manifestUrl="/ontologies/app/manifest.json" />
);
