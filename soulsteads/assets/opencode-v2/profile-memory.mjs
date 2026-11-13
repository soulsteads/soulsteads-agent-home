// Optional native OpenCode v2 hook. It never performs network or tool calls.
import fs from "node:fs/promises";
import {constants} from "node:fs";
import path from "node:path";

const ID = "soulstead.profile-memory";
const MEMORY_LIMIT = 64 * 1024;
const CONFIG_LIMIT = 1024 * 1024;
const FAILURE = "Profile memory is unavailable";
const STAT_OPTIONS = {bigint: true};
const CURRENT_UID = typeof process.getuid === "function" ? BigInt(process.getuid()) : null;

function requireFixedWorkspace(workspace) {
  if (typeof workspace !== "string" || !path.isAbsolute(workspace) ||
      workspace === path.sep || path.normalize(workspace) !== workspace ||
      workspace.endsWith(path.sep)) {
    throw new Error("Profile memory requires a fixed absolute workspace");
  }
  return workspace;
}

function requireFixedPath(pathname) {
  if (typeof pathname !== "string" || !path.isAbsolute(pathname) ||
      pathname === path.sep || path.normalize(pathname) !== pathname ||
      pathname.endsWith(path.sep)) {
    throw new Error();
  }
  return pathname;
}

function sameFileIdentity(left, right) {
  return left.dev === right.dev && left.ino === right.ino &&
    left.mode === right.mode && left.uid === right.uid &&
    left.nlink === right.nlink && left.size === right.size &&
    left.mtimeNs === right.mtimeNs && left.ctimeNs === right.ctimeNs;
}

function sameDirectoryIdentity(left, right) {
  return left.dev === right.dev && left.ino === right.ino &&
    left.mode === right.mode && left.uid === right.uid;
}

function requirePrivateDirectory(stat) {
  if (CURRENT_UID === null || !stat.isDirectory() ||
      (stat.uid !== CURRENT_UID && stat.uid !== 0n) || (stat.mode & 0o022n)) {
    throw new Error(FAILURE);
  }
}

async function workspaceSnapshot(workspace) {
  // Node lacks descriptor-relative directory traversal. These no-follow lexical
  // checks plus final rebinds fail closed on observed replacement, but cannot
  // eliminate a namespace race after the last check and before injection.
  if (workspace === path.sep) return [];
  const components = workspace.slice(1).split("/");
  let current = path.sep;
  const snapshot = [];
  for (const component of components) {
    current = path.join(current, component);
    const stat = await fs.lstat(current, STAT_OPTIONS);
    requirePrivateDirectory(stat);
    snapshot.push([current, stat]);
  }
  return snapshot;
}

async function verifyWorkspaceSnapshot(snapshot) {
  for (const [name, expected] of snapshot) {
    const actual = await fs.lstat(name, STAT_OPTIONS);
    if (!sameDirectoryIdentity(expected, actual)) throw new Error(FAILURE);
  }
}

function requireOwnedLeaf(stat, limit) {
  if (CURRENT_UID === null || !stat.isFile() || stat.uid !== CURRENT_UID ||
      (stat.mode & 0o077n) || stat.nlink !== 1n || stat.size > BigInt(limit)) {
    throw new Error(FAILURE);
  }
}

async function boundedRead(handle, expected, limit) {
  const bytes = Buffer.alloc(limit + 1);
  let length = 0;
  while (length <= limit) {
    const {bytesRead} = await handle.read(bytes, length, bytes.length - length, null);
    if (bytesRead === 0) break;
    length += bytesRead;
  }
  if (length > limit || BigInt(length) !== expected.size) throw new Error(FAILURE);
  return bytes.subarray(0, length).toString("utf8");
}

async function readOwnedPath(pathname, limit) {
  const workspace = await workspaceSnapshot(path.dirname(pathname));
  const namedBefore = await fs.lstat(pathname, STAT_OPTIONS);
  requireOwnedLeaf(namedBefore, limit);
  const handle = await fs.open(pathname, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const before = await handle.stat(STAT_OPTIONS);
    requireOwnedLeaf(before, limit);
    if (!sameFileIdentity(namedBefore, before)) throw new Error(FAILURE);
    const text = await boundedRead(handle, before, limit);
    const after = await handle.stat(STAT_OPTIONS);
    const namedAfter = await fs.lstat(pathname, STAT_OPTIONS);
    requireOwnedLeaf(after, limit);
    if (!sameFileIdentity(before, after) || !sameFileIdentity(before, namedAfter)) throw new Error(FAILURE);
    await verifyWorkspaceSnapshot(workspace);
    return {text, pathname, identity: before, workspace};
  } finally {
    await handle.close();
  }
}

async function readOwnedFile(workspace, name) {
  return readOwnedPath(path.join(workspace, name), MEMORY_LIMIT);
}

async function verifyRead(snapshot) {
  const named = await fs.lstat(snapshot.pathname, STAT_OPTIONS);
  requireOwnedLeaf(named, MEMORY_LIMIT);
  if (!sameFileIdentity(snapshot.identity, named)) throw new Error(FAILURE);
  await verifyWorkspaceSnapshot(snapshot.workspace);
}

async function loadMemory(workspace) {
  try {
    const rules = await readOwnedFile(workspace, "MEMORY-RULES.md");
    const memory = await readOwnedFile(workspace, "MEMORY.md");
    await verifyRead(rules);
    await verifyRead(memory);
    return `Profile memory rules:\n<profile-memory-rules>\n${rules.text}\n</profile-memory-rules>\n\n<profile-memory>\n${memory.text}\n</profile-memory>`;
  } catch {
    throw new Error(FAILURE);
  }
}

async function workspaceFromEnvironment() {
  if (process.env.SOULSTEAD_MEMORY_WORKSPACE) {
    return requireFixedWorkspace(process.env.SOULSTEAD_MEMORY_WORKSPACE);
  }
  try {
    const configPath = requireFixedPath(process.env.OPENCODE_CONFIG);
    const configSnapshot = await readOwnedPath(configPath, CONFIG_LIMIT);
    const config = JSON.parse(configSnapshot.text);
    const matches = Array.isArray(config.instructions) ? config.instructions.filter(item =>
      typeof item === "string" && path.isAbsolute(item) &&
      path.normalize(item) === item && item.endsWith(`${path.sep}MEMORY.md`)) : [];
    if (matches.length !== 1) throw new Error();
    return requireFixedWorkspace(path.dirname(matches[0]));
  } catch {
    throw new Error("Profile memory requires a fixed absolute workspace");
  }
}

export function createProfileMemoryPlugin({workspace}) {
  workspace = requireFixedWorkspace(workspace);
  return {
    id: ID,
    async setup(ctx) {
      const inject = async input => {
        const block = await loadMemory(workspace);
        if (!Array.isArray(input.system)) input.system = [];
        if (!input.system.some(part => part?.type === "text" && part.text === block)) {
          input.system.push({type: "text", text: block});
        }
      };
      for (const kind of ["context", "compaction", "generate"]) {
        await ctx.session.hook(kind, inject);
      }
    },
  };
}

export default {
  id: ID,
  async setup(ctx) {
    return createProfileMemoryPlugin({workspace: await workspaceFromEnvironment()}).setup(ctx);
  },
};
