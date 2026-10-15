// Compiles every userstyle of an import.json with less.js, injecting the @var defaults the
// way Stylus does for the less preprocessor (`@name: value;` before the source).
// Usage: node tests/stylus-compile.js build/stylus/import.json
// less comes from LESS_MODULE (path to the package) or the normal require() lookup.
// Test with a recent less too: Stylus bundles a newer one than upstream's 4.2.2, and it is
// stricter (it rejected pronouns.cc and google-drive until generate.fix_upstream).
const fs = require("fs");
const less = require(process.env.LESS_MODULE || "less");

function value(v) {
  switch (v.type) {
    case "select": return v.options.find((o) => o.name === v.default).value;
    case "checkbox": return v.default;
    case "range": return `${v.default}${v.units ?? ""}`;
    case "text": return JSON.stringify(v.default);
    default: throw new Error(`unsupported @var type: ${v.type}`);
  }
}

(async () => {
  const styles = JSON.parse(fs.readFileSync(process.argv[2], "utf8")).slice(1);
  let failed = 0;
  for (const s of styles) {
    const vars = Object.values(s.usercssData.vars ?? {});
    const prelude = vars.map((v) => `@${v.name}: ${value(v)};\n`).join("");
    try {
      await less.render(prelude + s.sourceCode);
    } catch (e) {
      failed++;
      console.log(`FALHOU: ${s.name}: ${e.message} (linha ${e.line})`);
    }
  }
  console.log(`less ${less.version.join(".")}: ${styles.length - failed}/${styles.length} compilam`);
  process.exit(failed ? 1 : 0);
})();
