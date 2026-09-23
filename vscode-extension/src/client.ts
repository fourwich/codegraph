import { execFile } from "child_process";
import { promisify } from "util";
import type { IndexResult, WhyResult } from "./types";

const execFileAsync = promisify(execFile);

export async function runWhy(
  cliPath: string,
  file: string,
  line: number,
  backend: string
): Promise<WhyResult | null> {
  const args = ["why", `${file}:${line}`, "--backend", backend, "--json"];
  const { stdout } = await execFileAsync(cliPath, args, {
    maxBuffer: 8 * 1024 * 1024,
    encoding: "utf8",
  });
  return JSON.parse(stdout) as WhyResult;
}

export async function runIndex(
  cliPath: string,
  workspace: string,
  backend: string
): Promise<IndexResult> {
  const args = ["index", workspace, "--backend", backend, "--json"];
  const { stdout } = await execFileAsync(cliPath, args, {
    maxBuffer: 16 * 1024 * 1024,
    encoding: "utf8",
  });
  return JSON.parse(stdout) as IndexResult;
}
