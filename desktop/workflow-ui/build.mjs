import { build } from "esbuild";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const output = path.resolve("../tradingagents/web/static/vendor/workflow-tools");
fs.mkdirSync(output, {recursive: true});
const result = await build({entryPoints: ["workflow-ui/index.js"], bundle: true, minify: true,
  format: "iife", globalName: "WorkflowTools", platform: "browser", target: ["es2020"],
  outfile: path.join(output, "workflow-tools.js"), metafile: true, legalComments: "none"});
const packages = new Map();
for (const input of Object.keys(result.metafile.inputs)) {
  let dir = path.dirname(path.resolve(input));
  while (dir.includes(`${path.sep}node_modules${path.sep}`)) {
    const manifest = path.join(dir, "package.json");
    if (fs.existsSync(manifest)) {
      const pkg = JSON.parse(fs.readFileSync(manifest, "utf8"));
      if (pkg.name && pkg.version) packages.set(`${pkg.name}@${pkg.version}`, {dir, pkg});
      break;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
}
let notices = "Third-party licenses for the bundled workflow toolkit\n\n";
for (const [name, {dir, pkg}] of [...packages].sort(([a], [b]) => a.localeCompare(b))) {
  notices += `\n=== ${name} (${pkg.license || "see license"}) ===\n`;
  const files = fs.readdirSync(dir).filter(file => /^(license|licence|copying|notice)(\.|$)/i.test(file));
  for (const file of files) notices += `\n--- ${file} ---\n${fs.readFileSync(path.join(dir, file), "utf8")}\n`;
  if (!files.length) notices += `License: ${pkg.license || "not specified"}; ${pkg.repository?.url || pkg.homepage || "see package"}\n`;
}
fs.writeFileSync(path.join(output, "THIRD-PARTY-NOTICES.txt"), notices);
