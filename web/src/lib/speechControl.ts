/** Hungarian/English stop phrases, independent of the microphone runtime. */
function plain(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}
export function isSpeechStop(text: string): boolean {
  const s = plain(text);
  if (/\b(?:ne allj|ne allitsd|ne hagyd abba|don't stop|do not stop)\b/.test(s)) return false;
  return /\b(?:allj|allitsd le|hagyd abba|eleg|hallgass|csendet|csond|csend|megse|cancel|nevermind|never\s*mind|shut\s*up|stop(?:\s+(?:talking|speaking))?|be\s+quiet|quiet|enough|hush)\b/.test(s);
}
export function isSleepRequest(text: string): boolean {
  return /\b(?:ne figyelj|ne hallgatozz|alvo mod|pihenj|ennyi volt|stop listening|go to sleep|jarvis stop|sleep mode|nevermind|never mind|that's all|that is all)\b/.test(plain(text));
}

/** Abortable fetch ownership. Old requests must never play after stop. */
export class SpeechRequests {
  private generation = 0;
  private requests = new Set<AbortController>();
  begin() {
    const generation = this.generation;
    const controller = new AbortController();
    this.requests.add(controller);
    return {
      signal: controller.signal,
      current: () => generation === this.generation && !controller.signal.aborted,
      finish: () => this.requests.delete(controller),
    };
  }
  cancel() {
    this.generation++;
    for (const request of this.requests) request.abort();
    this.requests.clear();
  }
}

/** Keep parallel synthesis responses in their original sentence order. */
export class OrderedSpeech<T> {
  private generation = 0;
  private issued = 0;
  private next = 0;
  private ready = new Map<number, T | null>();
  reserve() { return { generation: this.generation, index: this.issued++ }; }
  complete(ticket: { generation: number; index: number }, value: T | null): T[] {
    if (ticket.generation !== this.generation || ticket.index < this.next) return [];
    this.ready.set(ticket.index, value);
    const result: T[] = [];
    while (this.ready.has(this.next)) {
      const item = this.ready.get(this.next);
      this.ready.delete(this.next++);
      if (item != null) result.push(item);
    }
    return result;
  }
  reset() { this.generation++; this.issued = 0; this.next = 0; this.ready.clear(); }
}
