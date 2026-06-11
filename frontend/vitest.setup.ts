/**
 * Vitest setup file.
 *
 * Node 25+ ships a built-in `localStorage` that is an empty object
 * unless `--localstorage-file` is set to a valid path. That stub
 * shadows the one jsdom installs, so `localStorage.setItem` etc.
 * become undefined inside tests. Replace it with a minimal in-memory
 * implementation that mirrors the Web Storage API surface our app
 * actually uses (setItem / getItem / removeItem / clear).
 */

class MemoryStorage {
  private store = new Map<string, string>();

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  get length(): number {
    return this.store.size;
  }
}

const storage = new MemoryStorage();
const sessionStorage = new MemoryStorage();

Object.defineProperty(globalThis, 'localStorage', {
  value: storage,
  writable: true,
  configurable: true,
});
Object.defineProperty(globalThis, 'sessionStorage', {
  value: sessionStorage,
  writable: true,
  configurable: true,
});

// Also mirror onto window so `window.localStorage` works for code that
// reaches for the DOM property explicitly.
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    writable: true,
    configurable: true,
  });
  Object.defineProperty(window, 'sessionStorage', {
    value: sessionStorage,
    writable: true,
    configurable: true,
  });
}
