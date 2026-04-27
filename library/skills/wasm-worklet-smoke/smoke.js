#!/usr/bin/env node
// wasm-worklet-smoke: headless Playwright smoke test for an Emscripten + AudioWorklet build.
'use strict';

const { chromium } = require('playwright');
const { execSync, spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

// ── Argument parsing ──────────────────────────────────────────────────────────

const defaults = {
    buildDir:     'build/web',
    port:         8001,
    freq:         440,
    makeTarget:   'synth-wasm',
    rebuild:      true,
    audioCheck:   true,
    timeout:      15000,
    captureDelay: 200,
};

const args = { ...defaults };

for (let i = 2; i < process.argv.length; i++) {
    const a = process.argv[i];
    switch (a) {
        case '--build-dir':     args.buildDir     = process.argv[++i]; break;
        case '--port':          args.port         = parseInt(process.argv[++i], 10); break;
        case '--freq':          args.freq         = parseFloat(process.argv[++i]); break;
        case '--make-target':   args.makeTarget   = process.argv[++i]; break;
        case '--no-rebuild':    args.rebuild       = false; break;
        case '--no-audio-check': args.audioCheck  = false; break;
        case '--timeout':       args.timeout      = parseInt(process.argv[++i], 10); break;
        case '--capture-delay': args.captureDelay = parseInt(process.argv[++i], 10); break;
        default:
            console.error(`Unknown argument: ${a}`);
            process.exit(1);
    }
}

// ── Utilities ─────────────────────────────────────────────────────────────────

let passed = 0;
let failed = 0;
const errors = [];

function ok(msg)   { console.log(`  [PASS] ${msg}`); passed++; }
function fail(msg) { console.log(`  [FAIL] ${msg}`); failed++; errors.push(msg); }
function info(msg) { console.log(`  [INFO] ${msg}`); }

// Simple static file server
function startServer(dir, port) {
    const mimeTypes = {
        '.html': 'text/html',
        '.js':   'application/javascript',
        '.wasm': 'application/wasm',
        '.css':  'text/css',
    };
    const server = http.createServer((req, res) => {
        const filePath = path.join(dir, req.url === '/' ? 'index.html' : req.url);
        fs.readFile(filePath, (err, data) => {
            if (err) {
                res.writeHead(404);
                res.end(`Not found: ${req.url}`);
                return;
            }
            const ext = path.extname(filePath);
            res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
            res.end(data);
        });
    });
    return new Promise((resolve, reject) => {
        server.listen(port, '127.0.0.1', () => resolve(server));
        server.on('error', reject);
    });
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function run() {
    console.log('');
    console.log('── WASM Worklet Smoke Test ──────────────────────────────────────────────');

    // Step 1: Build
    console.log('');
    console.log('── Step 1: Build ───────────────────────────────────────────────────────');
    if (args.rebuild) {
        info(`Running: make ${args.makeTarget}`);
        try {
            execSync(`make ${args.makeTarget}`, { stdio: 'inherit' });
            ok(`make ${args.makeTarget} succeeded`);
        } catch (e) {
            fail(`make ${args.makeTarget} failed`);
            summary();
            process.exit(1);
        }
    } else {
        info('Skipping build (--no-rebuild)');
    }

    // Verify artifacts exist
    const jsFile   = path.join(args.buildDir, 'synth.js');
    const wasmFile = path.join(args.buildDir, 'synth.wasm');
    if (!fs.existsSync(jsFile))   { fail(`Missing: ${jsFile}`);   summary(); process.exit(1); }
    if (!fs.existsSync(wasmFile)) { fail(`Missing: ${wasmFile}`); summary(); process.exit(1); }
    ok(`Artifacts present: synth.js, synth.wasm`);

    // Step 2: Start HTTP server
    console.log('');
    console.log('── Step 2: HTTP server ─────────────────────────────────────────────────');
    let server;
    try {
        server = await startServer(path.resolve(args.buildDir), args.port);
        ok(`Server listening on http://localhost:${args.port}`);
    } catch (e) {
        fail(`Failed to start HTTP server: ${e.message}`);
        summary();
        process.exit(1);
    }

    const url = `http://localhost:${args.port}`;

    // Step 3: Headless browser test
    console.log('');
    console.log('── Step 3: Browser integration ─────────────────────────────────────────');

    const browser = await chromium.launch({
        args: ['--autoplay-policy=no-user-gesture-required', '--no-sandbox'],
    });

    const consoleErrors = [];
    const pageErrors    = [];
    let engineReady     = false;

    try {
        const page = await browser.newPage();

        page.on('console', msg => {
            if (msg.type() === 'error') {
                consoleErrors.push(msg.text());
                info(`console.error: ${msg.text()}`);
            } else {
                info(`console.log: ${msg.text()}`);
                if (msg.text().includes('WASM engine initialised')) {
                    engineReady = true;
                }
            }
        });

        page.on('pageerror', err => {
            pageErrors.push(err.message);
            info(`pageerror: ${err.message}`);
        });

        info(`Navigating to ${url}`);
        await page.goto(url);

        // Click Start Audio
        await page.click('#start');
        info('Clicked #start');

        // Poll for engine initialisation
        const deadline = Date.now() + args.timeout;
        while (!engineReady && Date.now() < deadline) {
            await new Promise(r => setTimeout(r, 200));
        }

        if (engineReady) {
            ok('WASM engine initialised');
        } else {
            fail(`Timeout: WASM engine did not initialise within ${args.timeout}ms`);
        }

        // Console error check
        if (consoleErrors.length === 0) {
            ok('No console.error events');
        } else {
            fail(`${consoleErrors.length} console.error event(s) detected`);
        }

        if (pageErrors.length === 0) {
            ok('No uncaught page errors');
        } else {
            fail(`${pageErrors.length} pageerror event(s) detected`);
        }

        // Step 4: Audio output check
        if (args.audioCheck && engineReady) {
            console.log('');
            console.log('── Step 4: Audio output check ──────────────────────────────────────────');

            // Check that main.js exposed window.__audioCtx and window.__synthNode
            const exposed = await page.evaluate(() => {
                return !!(window.__audioCtx && window.__synthNode);
            });

            if (!exposed) {
                fail(
                    'window.__audioCtx / window.__synthNode not exposed. ' +
                    'Add `window.__audioCtx = audioCtx; window.__synthNode = synthNode;` ' +
                    'to main.js after the AudioWorkletNode is ready. ' +
                    'Or pass --no-audio-check to skip this step.'
                );
            } else {
                // Wait for capture delay (catch envelope decay tail)
                await new Promise(r => setTimeout(r, args.captureDelay));

                const audioResult = await page.evaluate((captureDelay) => {
                    const audioCtx  = window.__audioCtx;
                    const synthNode = window.__synthNode;

                    const analyser = audioCtx.createAnalyser();
                    analyser.fftSize = 2048;

                    synthNode.disconnect();
                    synthNode.connect(analyser);
                    analyser.connect(audioCtx.destination);

                    return new Promise(resolve => {
                        setTimeout(() => {
                            const timeBuf = new Float32Array(analyser.fftSize);
                            analyser.getFloatTimeDomainData(timeBuf);

                            let maxAbs = 0;
                            for (let i = 0; i < timeBuf.length; i++) {
                                const a = Math.abs(timeBuf[i]);
                                if (a > maxAbs) maxAbs = a;
                            }

                            const freqBuf = new Float32Array(analyser.frequencyBinCount);
                            analyser.getFloatFrequencyData(freqBuf);

                            const sampleRate = audioCtx.sampleRate;

                            // Find peak frequency bin
                            let peakBin = 0;
                            let peakDb  = -Infinity;
                            for (let i = 1; i < freqBuf.length; i++) {
                                if (freqBuf[i] > peakDb) { peakDb = freqBuf[i]; peakBin = i; }
                            }
                            const binHz    = sampleRate / analyser.fftSize;
                            const peakFreq = peakBin * binHz;

                            resolve({ maxAbs, peakFreq, sampleRate, binHz });
                        }, 100);
                    });
                }, args.captureDelay);

                if (audioResult.maxAbs > 0.01) {
                    ok(`Non-silent audio detected (peak amplitude: ${audioResult.maxAbs.toFixed(4)})`);
                } else {
                    fail(`Silent audio output (peak amplitude: ${audioResult.maxAbs.toFixed(4)} ≤ 0.01)`);
                }

                if (args.freq > 0) {
                    const tolerance = audioResult.binHz * 1.5;
                    const diff = Math.abs(audioResult.peakFreq - args.freq);
                    if (diff <= tolerance) {
                        ok(`Fundamental frequency: ${audioResult.peakFreq.toFixed(1)} Hz (expected ~${args.freq} Hz)`);
                    } else {
                        fail(
                            `Fundamental frequency: ${audioResult.peakFreq.toFixed(1)} Hz, ` +
                            `expected ~${args.freq} Hz (diff ${diff.toFixed(1)} Hz > tolerance ${tolerance.toFixed(1)} Hz)`
                        );
                    }
                }
            }
        }

    } finally {
        await browser.close();
        await new Promise(resolve => server.close(resolve));
    }

    summary();
    process.exit(failed > 0 ? 1 : 0);
}

function summary() {
    console.log('');
    console.log('────────────────────────────────────────────────────────────────────────');
    if (failed === 0) {
        console.log(`SMOKE TEST PASSED: ${passed} checks passed`);
    } else {
        console.log(`SMOKE TEST FAILED: ${passed} passed, ${failed} failed`);
        for (const e of errors) console.log(`  - ${e}`);
    }
}

run().catch(err => {
    console.error('Unexpected error:', err);
    process.exit(1);
});
