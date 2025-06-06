/// <reference types="vitest" />
import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { exec } from 'child_process'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Custom plugin to add test endpoint
    {
      name: 'test-runner',
      configureServer(server) {
        server.middlewares.use('/api/run-tests', (req, res) => {
          if (req.method !== 'POST') {
            res.statusCode = 405
            res.end('Method not allowed')
            return
          }

          res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
          })

          // Run vitest with streaming output
          const testProcess = exec('npm run test -- --run --reporter=verbose', {
            cwd: process.cwd()
          })

          testProcess.stdout?.on('data', (data) => {
            const lines = data.toString().split('\n').filter((line: string) => line.trim())
            lines.forEach((line: string) => {
              res.write(`data: ${JSON.stringify({ type: 'output', message: line, timestamp: new Date().toISOString() })}\n\n`)
            })
          })

          testProcess.stderr?.on('data', (data) => {
            const lines = data.toString().split('\n').filter((line: string) => line.trim())
            lines.forEach((line: string) => {
              res.write(`data: ${JSON.stringify({ type: 'output', message: line, timestamp: new Date().toISOString() })}\n\n`)
            })
          })

          testProcess.on('close', (code) => {
            res.write(`data: ${JSON.stringify({ 
              type: 'completed', 
              exit_code: code, 
              status: code === 0 ? 'completed' : 'failed',
              timestamp: new Date().toISOString() 
            })}\n\n`)
            res.end()
          })

          testProcess.on('error', (error) => {
            res.write(`data: ${JSON.stringify({ 
              type: 'error', 
              message: error.message, 
              timestamp: new Date().toISOString() 
            })}\n\n`)
            res.end()
          })

          req.on('close', () => {
            testProcess.kill()
          })
        })
      }
    }
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './test/setup.ts',
    include: ['test/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    exclude: ['node_modules', 'dist', '.git', '.cache'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData.ts',
        '**/*.test.{ts,tsx}',
      ],
    },
  },
});
