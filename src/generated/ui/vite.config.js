import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const engine = '/home/warp/Documents/Universities/IPB/3_Investigacao/SMARTLEM/4_ProjectImplementations/PlatformBuilder/OntologyToUI';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@smart-lem/ontology-to-ui': path.join(engine, 'src', 'index.js') },
    dedupe: ['react', 'react-dom'],
  },
  server: { fs: { allow: ['.', engine] } },
});
