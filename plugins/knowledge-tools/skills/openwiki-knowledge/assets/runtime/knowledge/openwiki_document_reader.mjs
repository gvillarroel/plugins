// Closed, network-free exact byte transport for approved document paths.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {once} from 'node:events';

const MAX_CONTROL_BYTES = 1048576;
const MAX_FILE_BYTES = 268435456;
const allowed = new Set();
let buffer = Buffer.alloc(0);
let tasks = Promise.resolve();

async function send(value) {
  if (!process.stdout.write(JSON.stringify(value) + '\n')) await once(process.stdout, 'drain');
}

function physicalFile(filename) {
  const stat = fs.lstatSync(filename);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('not-regular');
  let parent = path.dirname(filename);
  while (true) {
    const info = fs.lstatSync(parent);
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error('linked-parent');
    const next = path.dirname(parent);
    if (next === parent) break;
    parent = next;
  }
  if (stat.size > MAX_FILE_BYTES) throw new Error('file-window');
  return stat;
}

async function handle(request) {
  const id = request && Number.isSafeInteger(request.id) && request.id > 0 ? request.id : null;
  try {
    if (!request || typeof request !== 'object' || Array.isArray(request) || id === null) throw new Error('request');
    if (request.op === 'authorize') {
      if (Object.keys(request).sort().join(',') !== 'id,op,paths' || !Array.isArray(request.paths) || !request.paths.length) throw new Error('authorize');
      for (const filename of request.paths) {
        if (typeof filename !== 'string' || filename.length > 32768 || !path.isAbsolute(filename) || path.normalize(filename) !== filename || filename.includes('\0')) throw new Error('path');
      }
      for (const filename of request.paths) allowed.add(filename);
      await send({id, type: 'authorized', count: request.paths.length});
      return;
    }
    if (request.op !== 'read' || Object.keys(request).sort().join(',') !== 'id,op,path' || !allowed.has(request.path)) throw new Error('unapproved');
    const stat = physicalFile(request.path);
    await send({id, type: 'start', bytes: stat.size});
    const hash = createHash('sha256');
    let offset = 0;
    // Each invocation opens the current file anew. No original byte cache exists.
    const stream = fs.createReadStream(request.path, {highWaterMark: 65536});
    for await (const data of stream) {
      if (offset + data.length > stat.size) throw new Error('changed-size');
      hash.update(data);
      await send({id, type: 'chunk', offset, data: data.toString('base64')});
      offset += data.length;
    }
    if (offset !== stat.size) throw new Error('changed-size');
    await send({id, type: 'end', bytes: offset, sha256: hash.digest('hex')});
  } catch {
    await send({id, type: 'error', code: 'exact-read-failed'});
  }
}

process.stdin.on('data', data => {
  buffer = Buffer.concat([buffer, data]);
  let newline;
  while ((newline = buffer.indexOf(10)) !== -1) {
    if (newline + 1 > MAX_CONTROL_BYTES) process.exit(2);
    const line = buffer.subarray(0, newline);
    buffer = buffer.subarray(newline + 1);
    tasks = tasks.then(async () => {
      try { await handle(JSON.parse(line.toString('utf8'))); }
      catch { await send({id: null, type: 'error', code: 'invalid-request'}); }
    });
  }
  if (buffer.length > MAX_CONTROL_BYTES) process.exit(2);
});
process.stdin.on('end', () => tasks.finally(() => process.exit(buffer.length ? 2 : 0)));
