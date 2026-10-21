import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const source = readFileSync(new URL('../src/lib/speechControl.ts', import.meta.url), 'utf8');
const {outputText} = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020}});
const {isSpeechStop, isSleepRequest, SpeechRequests, OrderedSpeech} = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('Hungarian and English speech stop phrases', () => {
  for (const phrase of ['Állj!', 'Jarvis, állítsd le!', 'Elég.', 'Mégse', 'Hagyd abba', 'csend', 'Stop talking', 'cancel']) assert.equal(isSpeechStop(phrase), true, phrase);
  for (const phrase of ['ne állj meg', 'ne állítsd le', 'folytasd a munkát', 'a csendes szoba', 'megsemmisítés', 'do not stop']) assert.equal(isSpeechStop(phrase), false, phrase);
});
test('Hungarian sleep phrases', () => {
  assert.equal(isSleepRequest('Jarvis, pihenj!'), true);
  assert.equal(isSleepRequest('Ne figyelj most.'), true);
  assert.equal(isSleepRequest('Beszélgessünk.'), false);
});
test('cancellation aborts in-flight fetches and rejects stale playback', () => {
  const gate = new SpeechRequests();
  const first = gate.begin();
  const second = gate.begin();
  assert.equal(first.current(), true);
  gate.cancel();
  assert.equal(first.signal.aborted, true);
  assert.equal(second.current(), false);
  first.finish();
  const next = gate.begin();
  assert.equal(next.current(), true);
  assert.equal(next.signal.aborted, false);
  second.finish();
  assert.equal(next.current(), true);
});

test('parallel synthesis preserves sentence order and skips failed segments', () => {
  const queue = new OrderedSpeech();
  const first = queue.reserve(), second = queue.reserve(), third = queue.reserve();
  assert.deepEqual(queue.complete(third, 'harmadik'), []);
  assert.deepEqual(queue.complete(second, null), []);
  assert.deepEqual(queue.complete(first, 'első'), ['első', 'harmadik']);
  assert.deepEqual(queue.complete(first, null), []);
  const old = queue.reserve();
  queue.reset();
  const next = queue.reserve();
  assert.deepEqual(queue.complete(old, 'régi'), []);
  assert.deepEqual(queue.complete(next, 'új'), ['új']);
});
