import path from 'node:path';

const keys = ['approval_policy', 'approvals_reviewer', 'sandbox_mode'];
const values = {
  approval_policy: ['on-request', 'never'],
  approvals_reviewer: ['user', 'auto_review'],
  sandbox_mode: ['read-only', 'workspace-write', 'danger-full-access'],
};
const keyPattern = '(?:[A-Za-z0-9_-]+|"(?:\\\\.|[^"\\\\])*"|\'[^\']*\')';
const assignment = new RegExp('^(\\s*(' + keyPattern + ')\\s*=\\s*)("[^"\\r\\n]*"|\'[^\'\\r\\n]*\')(\\s*(?:#.*)?)$');
const ownedStart = new RegExp('^\\s*(' + keyPattern + ')\\s*([.=])');
const ownedTable = new RegExp('^\\s*\\[\\[?\\s*(' + keyPattern + ')(?=[.\\]\\s])');

function keyName(token) {
  if (token[0] === "'") return token.slice(1, -1);
  if (token[0] !== '"') return token;
  try {
    return JSON.parse(token.replace(/\\(\\|U([0-9A-Fa-f]{8}))/g, (match, escaped, hex) => hex ? JSON.stringify(String.fromCodePoint(parseInt(hex, 16))).slice(1, -1) : match));
  } catch { throw new Error('Invalid quoted TOML key; native configuration was not changed'); }
}

function scanLine(line, state) {
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (state.quote) {
      if (state.quote[0] === '"' && char === '\\') { i++; continue; }
      if (line.startsWith(state.quote, i)) {
        let length = state.quote.length;
        if (length === 3) while (length < 5 && line[i + length] === char) length++;
        i += length - 1; state.quote = null;
      }
    } else if (char === '#') break;
    else if (char === '"' || char === "'") {
      state.quote = line.startsWith(char.repeat(3), i) ? char.repeat(3) : char;
      i += state.quote.length - 1;
    } else if (char === '[' || char === '{') state.containers.push(char);
    else if (char === ']' || char === '}') {
      if (state.containers.pop() !== (char === ']' ? '[' : '{')) throw new Error('Unbalanced TOML container; native configuration was not changed');
    }
  }
  if (state.quote?.length === 1) throw new Error('Unclosed TOML string; native configuration was not changed');
}

function rootSettings(text) {
  const lines = text.replace(/^\uFEFF/, '').split(/(?<=\n)/);
  const settings = new Map();
  const state = { quote: null, containers: [] };
  let root = true;
  for (const [index, raw] of lines.entries()) {
    const line = raw.replace(/\r?\n$/, '');
    if (!state.quote && !state.containers.length) {
      const scoped = ownedTable.exec(line);
      if (scoped && keys.includes(keyName(scoped[1]))) throw new Error('Scoped Council-owned key is not supported: ' + keyName(scoped[1]));
      if (/^\s*\[/.test(line)) root = false;
      const start = root && ownedStart.exec(line);
      if (start && keys.includes(keyName(start[1]))) {
        const key = keyName(start[1]);
        if (start[2] === '.') throw new Error('Scoped Council-owned key is not supported: ' + key);
        if (settings.has(key)) throw new Error('Duplicate Council-owned key: ' + key);
        const match = assignment.exec(line);
        if (!match) throw new Error('Council-owned key must use a single-line string value: ' + key);
        settings.set(key, { index, prefix: match[1], value: match[3].slice(1, -1), suffix: match[4], ending: raw.slice(line.length) });
      }
    }
    scanLine(line, state);
  }
  if (state.quote || state.containers.length) throw new Error('Unclosed TOML structure; native configuration was not changed');
  return { lines, settings };
}

/** Merge only Council-owned root scalars; preserve all other TOML text verbatim. */
export function mergeCodexDefaults(existing, fragment) {
  const desired = rootSettings(fragment).settings;
  for (const key of keys) {
    if (!desired.has(key) || !values[key].includes(desired.get(key).value)) throw new Error('Invalid or missing Codex default: ' + key);
  }
  const { lines, settings } = rootSettings(existing);
  const ending = existing.includes('\r\n') ? '\r\n' : '\n';
  const missing = [];
  for (const key of keys) {
    const value = desired.get(key).value;
    const current = settings.get(key);
    if (!current) missing.push(key + ' = "' + value + '"' + ending);
    else if (current.value !== value) lines[current.index] = current.prefix + '"' + value + '"' + current.suffix + current.ending;
  }
  return (existing.startsWith('\uFEFF') ? '\uFEFF' : '') + missing.join('') + lines.join('');
}

function stringArray(text) {
  const tokens = [...text.matchAll(/"(?:\\.|[^"\\])*"|'[^']*'|#[^\r\n]*|\s+|./g)];
  const significant = tokens.filter(token => !/^\s|^#/.test(token[0]));
  const opening = significant.shift(), closing = significant.pop();
  if (opening?.[0] !== '[' || closing?.[0] !== ']') throw new Error('writable_roots must be a TOML string array');
  const values = [];
  let expectValue = true;
  for (const match of significant) {
    const token = match[0];
    if (expectValue) {
      if (!/^["']/.test(token)) throw new Error('writable_roots must contain only strings');
      values.push(keyName(token));
    } else if (token !== ',') throw new Error('Invalid writable_roots array separator');
    expectValue = !expectValue;
  }
  return {values, suffix: text.slice(closing.index + 1)};
}

/** Own only this table's writable_roots value. Preserve all other native text. */
export function mergeCodexWorkspaceRoots(existing, requiredRoots) {
  if (!Array.isArray(requiredRoots) || requiredRoots.some(root => typeof root !== 'string' || !path.isAbsolute(root))) throw new Error('Council writable roots must be absolute paths');
  if (!requiredRoots.length) return existing;
  rootSettings(existing); // Reuse the conservative string/container boundary validation.
  const ending = existing.includes('\r\n') ? '\r\n' : '\n';
  const lines = existing.replace(/^\uFEFF/, '').split(/(?<=\n)/);
  const state = {quote: null, containers: []};
  let inTable = false, tableIndex = -1, valueStart = -1, valueEnd = -1, prefix = '', suffix = '';
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index].replace(/\r?\n$/, '');
    if (!state.quote && !state.containers.length) {
      const table = line.match(new RegExp('^\\s*\\[\\s*(' + keyPattern + ')\\s*\\]\\s*(?:#.*)?$'));
      const ownedHeader = line.match(new RegExp('^\\s*\\[\\[?\\s*(' + keyPattern + ')(?=[.\\]\\s])'));
      if (ownedHeader && keyName(ownedHeader[1]) === 'sandbox_workspace_write' && !table) throw new Error('Unsupported sandbox_workspace_write table form');
      if (/^\s*\[/.test(line)) {
        inTable = !!table && keyName(table[1]) === 'sandbox_workspace_write';
        if (inTable) {
          if (tableIndex >= 0) throw new Error('Duplicate sandbox_workspace_write table');
          tableIndex = index;
        }
      }
      const scoped = line.match(new RegExp('^\\s*(' + keyPattern + ')\\s*[.=]'));
      if (scoped && keyName(scoped[1]) === 'sandbox_workspace_write') throw new Error('Use the sandbox_workspace_write table, not dotted or inline TOML');
      const entry = inTable && line.match(new RegExp('^(\\s*(' + keyPattern + ')\\s*)([.=])\\s*'));
      if (entry && keyName(entry[2]) === 'writable_roots') {
        if (entry[3] !== '=' || valueStart >= 0) throw new Error('Ambiguous writable_roots setting');
        valueStart = index;
        prefix = line.slice(0, entry[0].length);
      }
    }
    scanLine(line, state);
    if (valueStart >= 0 && valueEnd < 0 && !state.quote && !state.containers.length) {
      valueEnd = index;
    }
  }
  const oldValue = valueStart >= 0 ? lines.slice(valueStart, valueEnd + 1).join('').slice(prefix.length) : '[]';
  const parsed = stringArray(oldValue);
  const roots = parsed.values;
  suffix = parsed.suffix;
  const identity = value => process.platform === 'win32' ? path.resolve(value).toLowerCase() : path.resolve(value);
  const missing = requiredRoots.filter(root => !roots.some(value => identity(value) === identity(root)));
  if (!missing.length) return existing;
  const value = JSON.stringify([...roots, ...missing]);
  if (valueStart >= 0) lines.splice(valueStart, valueEnd - valueStart + 1, prefix + value + suffix);
  else if (tableIndex >= 0) {
    if (!lines[tableIndex].endsWith('\n')) lines[tableIndex] += ending;
    lines.splice(tableIndex + 1, 0, 'writable_roots = ' + value + ending);
  } else {
    if (lines.length && lines.at(-1) && !lines.at(-1).endsWith('\n')) lines[lines.length - 1] += ending;
    lines.push(ending + '[sandbox_workspace_write]' + ending + 'writable_roots = ' + value + ending);
  }
  return (existing.startsWith('\uFEFF') ? '\uFEFF' : '') + lines.join('');
}
