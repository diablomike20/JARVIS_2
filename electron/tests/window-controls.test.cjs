const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('desktop controls invoke real main-process handlers; preload rejects unknown IPC', () => {
  const handlers = new Map();
  const calls = [];
  const app = {requestSingleInstanceLock: () => false, quit() {}, on() {}};
  const ipcMain = {on: (name, fn) => handlers.set(name, fn), handle() {}};
  const context = vm.createContext({require: (name) => name === 'electron' ? {app, ipcMain} : require(name), process, console, __dirname: path.resolve(__dirname, '..'), setTimeout, clearTimeout, Buffer});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../main.cjs'), 'utf8'), context);
  context.testWindow = {
    minimized: false, maximized: false,
    minimize() { this.minimized = true; },
    isMaximized() { return this.maximized; },
    maximize() { this.maximized = true; },
    unmaximize() { this.maximized = false; },
  };
  vm.runInContext('mainWindow = testWindow; installIpc()', context);
  const preload = vm.createContext({require: () => ({
    contextBridge: {exposeInMainWorld: (_, api) => {context.bridge = api;}},
    ipcRenderer: {send: name => { calls.push(name); handlers.get(name)?.(); }},
  })});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../preload.cjs'), 'utf8'), preload);
  context.bridge.send('jarvis:minimize');
  assert.equal(context.testWindow.minimized, true);
  context.bridge.send('jarvis:maximize');
  assert.equal(context.testWindow.maximized, true);
  context.bridge.send('jarvis:maximize');
  assert.equal(context.testWindow.maximized, false);
  context.bridge.send('arbitrary:execute');
  assert.equal(calls.length, 3);
});
