#!/usr/bin/env node
/**
 * Start both backend and frontend servers concurrently
 * Backend starts first, then frontend once backend is ready
 */

const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

const BACKEND_PORT = 8000;
const BACKEND_HEALTH_URL = `http://localhost:${BACKEND_PORT}/health`;
const MAX_RETRIES = 30;
const RETRY_DELAY = 1000;

let backendProcess = null;
let frontendProcess = null;

// Cleanup on exit
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down servers...');
  if (frontendProcess) frontendProcess.kill();
  if (backendProcess) backendProcess.kill();
  process.exit(0);
});

process.on('SIGTERM', () => {
  if (frontendProcess) frontendProcess.kill();
  if (backendProcess) backendProcess.kill();
  process.exit(0);
});

/**
 * Check if backend is healthy
 */
function checkBackendHealth() {
  return new Promise((resolve) => {
    const req = http.get(BACKEND_HEALTH_URL, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

/**
 * Wait for backend to be ready
 */
async function waitForBackend(retries = MAX_RETRIES) {
  for (let i = 0; i < retries; i++) {
    const isHealthy = await checkBackendHealth();
    if (isHealthy) {
      console.log('✅ Backend is ready!\n');
      return true;
    }
    process.stdout.write(`⏳ Waiting for backend... (${i + 1}/${retries})\r`);
    await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
  }
  return false;
}

/**
 * Start the backend server
 */
function startBackend() {
  return new Promise((resolve, reject) => {
    console.log('🚀 Starting backend server...\n');
    
    const backendRoot = path.resolve(__dirname, '..', '..');
    const isWindows = process.platform === 'win32';
    
    // Use the start_backend.py script
    backendProcess = spawn(
      'python',
      ['start_backend.py'],
      {
        cwd: backendRoot,
        stdio: 'inherit',
        shell: isWindows
      }
    );

    backendProcess.on('error', (err) => {
      console.error('❌ Failed to start backend:', err.message);
      reject(err);
    });

    backendProcess.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        console.error(`❌ Backend exited with code ${code}`);
      }
    });

    // Give it a moment to start
    setTimeout(() => resolve(), 2000);
  });
}

/**
 * Start the frontend server
 */
function startFrontend() {
  console.log('🎨 Starting frontend server...\n');
  
  const isWindows = process.platform === 'win32';
  const npmCmd = isWindows ? 'npm.cmd' : 'npm';
  
  frontendProcess = spawn(
    npmCmd,
    ['run', 'dev:next'],
    {
      cwd: path.resolve(__dirname, '..'),
      stdio: 'inherit',
      shell: isWindows
    }
  );

  frontendProcess.on('error', (err) => {
    console.error('❌ Failed to start frontend:', err.message);
    process.exit(1);
  });

  frontendProcess.on('exit', (code) => {
    if (code !== 0 && code !== null) {
      console.error(`❌ Frontend exited with code ${code}`);
    }
    // If frontend exits, kill backend too
    if (backendProcess) backendProcess.kill();
    process.exit(code || 0);
  });
}

/**
 * Main execution
 */
async function main() {
  console.log('🔧 MarketPy Full Stack Startup\n');
  console.log('================================\n');

  try {
    // Start backend
    await startBackend();

    // Wait for backend to be healthy
    const backendReady = await waitForBackend();
    
    if (!backendReady) {
      console.error('\n❌ Backend failed to start within timeout period');
      console.error('   Check backend logs above for errors');
      if (backendProcess) backendProcess.kill();
      process.exit(1);
    }

    // Start frontend
    startFrontend();

    console.log('\n================================');
    console.log('✨ Both servers are running!\n');
    console.log(`   Backend:  http://localhost:${BACKEND_PORT}`);
    console.log('   Frontend: http://localhost:3000\n');
    console.log('Press Ctrl+C to stop both servers\n');

  } catch (error) {
    console.error('\n❌ Startup failed:', error.message);
    if (backendProcess) backendProcess.kill();
    if (frontendProcess) frontendProcess.kill();
    process.exit(1);
  }
}

main();
