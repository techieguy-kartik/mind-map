import {defineConfig,devices} from '@playwright/test';
export default defineConfig({
  testDir:'./tests/browser',fullyParallel:false,workers:1,
  use:{baseURL:'http://127.0.0.1:8001',trace:'retain-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
  webServer:{command:'ATLAS_DB=var/browser-tests.sqlite3 ATLAS_DAILY_INVESTIGATIONS=100 .venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8001',url:'http://127.0.0.1:8001/api/health',reuseExistingServer:false,timeout:30000},
});
