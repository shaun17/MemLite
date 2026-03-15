#!/usr/bin/env node
/**
 * Sync package.json version from pyproject.toml before npm publish.
 * Run automatically via the "prepublishOnly" lifecycle hook.
 */
import { readFileSync, writeFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "../../..");

const toml = readFileSync(resolve(root, "pyproject.toml"), "utf8");
const match = toml.match(/^version\s*=\s*"([^"]+)"/m);
if (!match) throw new Error("version not found in pyproject.toml");
const version = match[1];

const pkgPath = resolve(__dirname, "../package.json");
const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
pkg.version = version;
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");

console.log(`synced @wenrennow/memolite version → ${version}`);
