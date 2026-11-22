import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The GitHub Pages build (`pipeline/pages.py`) passes the deployment layout as
// BME_SITE: {"base": "/business-model-explorer/", "bundleBases": {...}}. It
// also stages the public files itself (bundles compacted and split across
// sites), so Vite does not copy public/ then. See src/site.ts.
const site = process.env.BME_SITE ? JSON.parse(process.env.BME_SITE) : undefined;

export default defineConfig({
  plugins: [react()],
  base: site?.base ?? "/",
  define: site ? { __SITE__: JSON.stringify(site) } : {},
  build: { copyPublicDir: !site },
});
