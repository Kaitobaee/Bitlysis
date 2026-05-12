import fs from "node:fs";
import path from "node:path";

const projectRoot = process.cwd();
const inputArg = process.argv[2] ?? "apps/web/public/animations/data.json";
const targetFrArg = Number(process.argv[3] ?? 30);

const inputPath = path.resolve(projectRoot, inputArg);
const raw = fs.readFileSync(inputPath, "utf8");
const data = JSON.parse(raw);

const originalFr = typeof data.fr === "number" && data.fr > 0 ? data.fr : targetFrArg;
const targetFr = Number.isFinite(targetFrArg) && targetFrArg > 0 ? targetFrArg : 30;
const frameRatio = targetFr / originalFr;

const stats = {
  removedExpressions: 0,
  scaledTimes: 0,
  scaledRanges: 0,
  updatedFr: 0,
};

function scaleFrame(value) {
  return Math.round(value * frameRatio * 1000) / 1000;
}

function isKeyframeObject(obj) {
  return Object.prototype.hasOwnProperty.call(obj, "t") && Object.prototype.hasOwnProperty.call(obj, "s");
}

function walk(node) {
  if (Array.isArray(node)) {
    for (const item of node) walk(item);
    return;
  }

  if (!node || typeof node !== "object") {
    return;
  }

  if (typeof node.x === "string") {
    delete node.x;
    stats.removedExpressions += 1;
  }

  if (typeof node.fr === "number") {
    node.fr = targetFr;
    stats.updatedFr += 1;
  }

  if (isKeyframeObject(node) && typeof node.t === "number") {
    node.t = scaleFrame(node.t);
    stats.scaledTimes += 1;
  }

  for (const key of ["ip", "op", "st"]) {
    if (typeof node[key] === "number") {
      node[key] = scaleFrame(node[key]);
      stats.scaledRanges += 1;
    }
  }

  for (const value of Object.values(node)) {
    walk(value);
  }
}

walk(data);

data.fr = targetFr;

fs.writeFileSync(inputPath, JSON.stringify(data));

console.log(
  JSON.stringify(
    {
      file: inputPath,
      originalFr,
      targetFr,
      durationSecondsBefore: Number((data.op / targetFr).toFixed(3)) * (targetFr / targetFr),
      stats,
    },
    null,
    2,
  ),
);
